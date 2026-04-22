function _tvDeleteDrawing(chartId, drawIdx) {
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds) return;
    var d = ds.drawings[drawIdx];
    if (!d) return;

    // Push undo entry before deleting
    var _undoChartId = chartId;
    var _undoDrawing = Object.assign({}, d);
    var _undoIdx = drawIdx;
    _tvPushUndo({
        label: 'Delete ' + (d.type || 'drawing'),
        undo: function() {
            var ds2 = window.__PYWRY_DRAWINGS__[_undoChartId];
            if (!ds2) return;
            var idx = Math.min(_undoIdx, ds2.drawings.length);
            ds2.drawings.splice(idx, 0, Object.assign({}, _undoDrawing));
            // Re-create native price line if hline
            if (_undoDrawing.type === 'hline') {
                var entry = window.__PYWRY_TVCHARTS__[_undoChartId];
                if (entry) {
                    var mainKey = Object.keys(entry.seriesMap)[0];
                    if (mainKey && entry.seriesMap[mainKey]) {
                        var pl = entry.seriesMap[mainKey].createPriceLine({
                            price: _undoDrawing.price, color: _undoDrawing.color,
                            lineWidth: _undoDrawing.lineWidth, lineStyle: _undoDrawing.lineStyle,
                            axisLabelVisible: true, title: '',
                        });
                        ds2.priceLines.splice(idx, 0, { seriesId: mainKey, priceLine: pl });
                    }
                }
            }
            _tvDeselectAll(_undoChartId);
        },
        redo: function() {
            var ds2 = window.__PYWRY_DRAWINGS__[_undoChartId];
            if (!ds2) return;
            for (var i = ds2.drawings.length - 1; i >= 0; i--) {
                if (ds2.drawings[i]._id === _undoDrawing._id) {
                    if (ds2.drawings[i].type === 'hline' && ds2.priceLines[i]) {
                        var entry = window.__PYWRY_TVCHARTS__[_undoChartId];
                        if (entry) {
                            var pl2 = ds2.priceLines[i];
                            var ser = entry.seriesMap[pl2.seriesId];
                            if (ser) try { ser.removePriceLine(pl2.priceLine); } catch(e) {}
                        }
                        ds2.priceLines.splice(i, 1);
                    }
                    ds2.drawings.splice(i, 1);
                    break;
                }
            }
            _tvDeselectAll(_undoChartId);
        },
    });

    // Remove native price line if hline
    if (d.type === 'hline' && ds.priceLines[drawIdx]) {
        var entry = window.__PYWRY_TVCHARTS__[chartId];
        if (entry) {
            var pl = ds.priceLines[drawIdx];
            var ser = entry.seriesMap[pl.seriesId];
            if (ser) try { ser.removePriceLine(pl.priceLine); } catch(e) {}
        }
        ds.priceLines.splice(drawIdx, 1);
    }
    ds.drawings.splice(drawIdx, 1);
    _drawSelectedIdx = -1;
    _drawSelectedChart = null;
    _tvHideFloatingToolbar();
    _tvRenderDrawings(chartId);
    if (window.pywry && window.pywry.emit) {
        window.pywry.emit('tvchart:drawing-deleted', { chartId: chartId, index: drawIdx });
    }
}

// ---- Sync native price line color for hlines ----
function _tvSyncPriceLineColor(chartId, drawIdx, color) {
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds || !ds.priceLines[drawIdx]) return;
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry) return;
    var pl = ds.priceLines[drawIdx];
    var ser = entry.seriesMap[pl.seriesId];
    if (ser) {
        try { ser.removePriceLine(pl.priceLine); } catch(e) {}
        var drw = ds.drawings[drawIdx];
        var newPl = ser.createPriceLine({
            price: drw.price,
            color: color,
            lineWidth: drw.lineWidth || 2,
            lineStyle: drw.lineStyle || 0,
            axisLabelVisible: drw.showPriceLabel !== false,
            title: drw.title || '',
        });
        ds.priceLines[drawIdx] = { seriesId: pl.seriesId, priceLine: newPl };
    }
}

// ---- Mouse interaction engine ----
function _tvEnableDrawing(chartId) {
    var ds = _tvEnsureDrawingLayer(chartId);
    if (!ds || ds._eventsAttached) return;
    ds._eventsAttached = true;

    var canvas = ds.canvas;
    var entry  = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry) return;
    var container = entry.container;

    // =========================================================================
    // Container-level listeners: work in CURSOR mode (canvas has ptr-events:none)
    // Events bubble up from the chart's own internal canvas through the container.
    // =========================================================================

    // --- Mouse move: hover highlight + drag (cursor mode) ---
    // Use CAPTURE phase so drag moves are intercepted before the chart.
    // NOTE: During drag, document-level handlers do the actual drag work.
    // This handler only blocks propagation during drag so the chart doesn't pan.
    container.addEventListener('mousemove', function(e) {
        // When a modal is open (interaction locked), never process hover/drag
        if (entry._interactionLocked) return;
        // During drag, the document-level handler processes movement.
        // Just block chart interaction here.
        if (_drawDragging && _drawSelectedChart === chartId) {
            e.preventDefault();
            e.stopPropagation();
            return;
        }

        // Hover detection (cursor mode only)
        if (ds._activeTool === 'cursor') {
            var rect = canvas.getBoundingClientRect();
            var mx = e.clientX - rect.left;
            var my = e.clientY - rect.top;
            var hitIdx = _tvHitTest(chartId, mx, my);
            if (hitIdx !== _drawHoverIdx) {
                _drawHoverIdx = hitIdx;
                _tvRenderDrawings(chartId);
            }
            // Cursor style feedback
            if (_drawSelectedIdx >= 0 && _drawSelectedChart === chartId) {
                var selD = ds.drawings[_drawSelectedIdx];
                if (selD) {
                    var ancs = _tvDrawAnchors(chartId, selD);
                    for (var ai = 0; ai < ancs.length; ai++) {
                        var dx = mx - ancs[ai].x, dy = my - ancs[ai].y;
                        if (dx * dx + dy * dy < 64) {
                            container.style.cursor = 'grab';
                            return;
                        }
                    }
                }
            }
            container.style.cursor = hitIdx >= 0 ? 'pointer' : '';
        }
    }, true);  // capture phase

    // --- Document-level drag handler (bound during startDrag, unbound in endDrag) ---
    // Using document-level ensures drag continues even when mouse leaves the container.
    var _boundDocDragMove = null;
    var _boundDocDragEnd  = null;

    function docDragMove(e) {
        if (!_drawDragging || _drawSelectedChart !== chartId) return;
        var rect = canvas.getBoundingClientRect();
        var mx = e.clientX - rect.left;
        var my = e.clientY - rect.top;
        e.preventDefault();

        var dd = ds.drawings[_drawSelectedIdx];
        if (!dd || dd.locked) { _tvRenderDrawings(chartId); return; }

        var series = _tvMainSeries(chartId);
        var ak = _drawDragging.anchor;

        if (ak === 'body') {
            // Pixel-based translation from drag start.
            // Use total pixel offset applied to the ORIGINAL anchor positions
            // to avoid accumulated time-rounding drift.
            var totalDx = mx - _drawDragging.startX;
            var totalDy = my - _drawDragging.startY;

            if (dd.type === 'hline') {
                if (_drawDragging._origPriceY !== null && series) {
                    var newP = series.coordinateToPrice(_drawDragging._origPriceY + totalDy);
                    if (newP !== null) dd.price = newP;
                }
            } else if (dd.type === 'vline') {
                if (_drawDragging._origPx1) {
                    var vNewC = _tvFromPixel(chartId, _drawDragging._origPx1.x + totalDx, 0);
                    if (vNewC && vNewC.time !== null) dd.t1 = vNewC.time;
                }
            } else if (dd.type === 'flat_channel') {
                if (_drawDragging._origPriceY !== null && _drawDragging._origPrice2Y !== null && series) {
                    var fcP1 = series.coordinateToPrice(_drawDragging._origPriceY + totalDy);
                    var fcP2 = series.coordinateToPrice(_drawDragging._origPrice2Y + totalDy);
                    if (fcP1 !== null && fcP2 !== null) { dd.p1 = fcP1; dd.p2 = fcP2; }
                }
            } else if ((dd.type === 'brush' || dd.type === 'highlighter' || dd.type === 'path' || dd.type === 'polyline') && dd.points && _drawDragging._origBrushPx) {
                var obp = _drawDragging._origBrushPx;
                var allOk = true;
                var newPts = [];
                for (var bdi = 0; bdi < obp.length; bdi++) {
                    if (!obp[bdi]) { allOk = false; break; }
                    var bNewC = _tvFromPixel(chartId, obp[bdi].x + totalDx, obp[bdi].y + totalDy);
                    if (!bNewC || bNewC.time === null || bNewC.price === null) { allOk = false; break; }
                    newPts.push({ t: bNewC.time, p: bNewC.price });
                }
                if (allOk) dd.points = newPts;
            } else {
                // Two-point (or three-point) tools: translate all anchors in pixel space
                if (_drawDragging._origPx1 && _drawDragging._origPx2) {
                    var newC1 = _tvFromPixel(chartId, _drawDragging._origPx1.x + totalDx, _drawDragging._origPx1.y + totalDy);
                    var newC2 = _tvFromPixel(chartId, _drawDragging._origPx2.x + totalDx, _drawDragging._origPx2.y + totalDy);
                    if (newC1 && newC1.time !== null && newC1.price !== null &&
                        newC2 && newC2.time !== null && newC2.price !== null) {
                        dd.t1 = newC1.time; dd.p1 = newC1.price;
                        dd.t2 = newC2.time; dd.p2 = newC2.price;
                    }
                    // Also translate third anchor if present
                    if (_drawDragging._origPx3) {
                        var newC3 = _tvFromPixel(chartId, _drawDragging._origPx3.x + totalDx, _drawDragging._origPx3.y + totalDy);
                        if (newC3 && newC3.time !== null && newC3.price !== null) {
                            dd.t3 = newC3.time; dd.p3 = newC3.price;
                        }
                    }
                }
            }
        } else {
            // Anchor drag: set the anchor directly from mouse position
            var coord = _tvFromPixel(chartId, mx, my);
            if (!coord || coord.time === null || coord.price === null) {
                _tvRenderDrawings(chartId);
                return;
            }
            if (ak === 'p1') { dd.t1 = coord.time; dd.p1 = coord.price; }
            else if (ak === 'p2') { dd.t2 = coord.time; dd.p2 = coord.price; }
            else if (ak === 'p3') { dd.t3 = coord.time; dd.p3 = coord.price; }
            else if (ak === 'price') { dd.price = coord.price; }
            else if (ak.indexOf('pt') === 0 && dd.points) {
                // Path/polyline vertex drag
                var ptIdx = parseInt(ak.substring(2));
                if (!isNaN(ptIdx) && ptIdx >= 0 && ptIdx < dd.points.length) {
                    dd.points[ptIdx] = { t: coord.time, p: coord.price };
                }
            }
        }

        _tvRenderDrawings(chartId);
        _tvRepositionToolbar(chartId);
    }

    // --- Mouse down: begin drag (select + drag in one motion, cursor mode) ---
    // Use CAPTURE phase so we fire before the chart and can block its panning.
    container.addEventListener('mousedown', function(e) {
        if (e.button !== 0) return;
        // When a modal is open (interaction locked), never start drawing drag
        if (entry._interactionLocked) return;
        if (ds._activeTool !== 'cursor') return;
        var rect = canvas.getBoundingClientRect();
        var mx = e.clientX - rect.left;
        var my = e.clientY - rect.top;

        // Helper: start dragging and block chart panning
        function startDrag(anchor, mx2, my2) {
            var dd = ds.drawings[_drawSelectedIdx];
            var series = _tvMainSeries(chartId);
            _drawDragging = {
                anchor: anchor, startX: mx2, startY: my2,
                // Store original anchor pixel positions at drag start
                _origPx1: null, _origPx2: null, _origPx3: null,
                _origPriceY: null, _origPrice2Y: null,
                _origBrushPx: null,
            };
            // Snapshot pixel positions for body drag
            if (anchor === 'body' && dd) {
                if (dd.type === 'hline' && series) {
                    _drawDragging._origPriceY = series.priceToCoordinate(dd.price);
                } else if (dd.type === 'vline') {
                    _drawDragging._origPx1 = _tvToPixel(chartId, dd.t1, 0);
                } else if (dd.type === 'flat_channel' && series) {
                    _drawDragging._origPriceY = series.priceToCoordinate(dd.p1);
                    _drawDragging._origPrice2Y = series.priceToCoordinate(dd.p2);
                } else if ((dd.type === 'brush' || dd.type === 'highlighter' || dd.type === 'path' || dd.type === 'polyline') && dd.points) {
                    _drawDragging._origBrushPx = [];
                    for (var bi = 0; bi < dd.points.length; bi++) {
                        _drawDragging._origBrushPx.push(
                            _tvToPixel(chartId, dd.points[bi].t, dd.points[bi].p)
                        );
                    }
                } else {
                    _drawDragging._origPx1 = dd.t1 !== undefined ? _tvToPixel(chartId, dd.t1, dd.p1) : null;
                    _drawDragging._origPx2 = dd.t2 !== undefined ? _tvToPixel(chartId, dd.t2, dd.p2) : null;
                    _drawDragging._origPx3 = dd.t3 !== undefined ? _tvToPixel(chartId, dd.t3, dd.p3) : null;
                }
            }
            // Block chart panning by making the overlay intercept events
            canvas.style.pointerEvents = 'auto';
            // Freeze chart interaction so crosshair/legend/axes don't move
            entry.chart.applyOptions({ handleScroll: false, handleScale: false });
            entry.chart.clearCrosshairPosition();
            container.style.cursor = anchor === 'body' ? 'move' : 'grabbing';
            // Bind document-level handlers so drag works even outside the container
            _boundDocDragMove = docDragMove;
            _boundDocDragEnd  = docDragEnd;
            document.addEventListener('mousemove', _boundDocDragMove, true);
            document.addEventListener('mouseup', _boundDocDragEnd, true);
            e.preventDefault();
            e.stopPropagation();
        }

        // If a drawing is already selected, try its anchors first
        if (_drawSelectedIdx >= 0 && _drawSelectedChart === chartId) {
            var selD = ds.drawings[_drawSelectedIdx];
            if (selD && !selD.locked) {
                var ancs = _tvDrawAnchors(chartId, selD);
                for (var ai = 0; ai < ancs.length; ai++) {
                    var adx = mx - ancs[ai].x, ady = my - ancs[ai].y;
                    if (adx * adx + ady * ady < 64) {
                        startDrag(ancs[ai].key, mx, my);
                        return;
                    }
                }
                if (_tvDrawHit(chartId, selD, mx, my, 8)) {
                    startDrag('body', mx, my);
                    return;
                }
            }
        }

        // Not on the selected drawing — hit-test all drawings to select + drag
        var hitIdx = _tvHitTest(chartId, mx, my);
        if (hitIdx >= 0) {
            var hitD = ds.drawings[hitIdx];
            if (hitD && !hitD.locked) {
                _drawSelectedIdx = hitIdx;
                _drawSelectedChart = chartId;
                _tvRenderDrawings(chartId);
                _tvShowFloatingToolbar(chartId, hitIdx);
                // Check anchors of new selection
                var hitAncs = _tvDrawAnchors(chartId, hitD);
                for (var hai = 0; hai < hitAncs.length; hai++) {
                    var hdx = mx - hitAncs[hai].x, hdy = my - hitAncs[hai].y;
                    if (hdx * hdx + hdy * hdy < 64) {
                        startDrag(hitAncs[hai].key, mx, my);
                        return;
                    }
                }
                startDrag('body', mx, my);
            }
        }
    }, true);  // capture phase

    // --- Mouse up: end drag ---
    function docDragEnd() {
        if (_drawDragging) {
            _drawDidDrag = true;
            _drawDragging = null;
            // Remove document-level handlers
            if (_boundDocDragMove) document.removeEventListener('mousemove', _boundDocDragMove, true);
            if (_boundDocDragEnd) document.removeEventListener('mouseup', _boundDocDragEnd, true);
            _boundDocDragMove = null;
            _boundDocDragEnd  = null;
            // Restore pointer-events so chart can pan/zoom again
            _tvApplyDrawingInteractionMode(ds);
            // Restore chart interaction
            entry.chart.applyOptions({ handleScroll: true, handleScale: true });
            container.style.cursor = '';
            _tvRenderDrawings(chartId);
            _tvRepositionToolbar(chartId);
            // Sync native price line if hline was dragged
            if (_drawSelectedIdx >= 0 && ds.drawings[_drawSelectedIdx] &&
                ds.drawings[_drawSelectedIdx].type === 'hline') {
                _tvSyncPriceLineColor(chartId, _drawSelectedIdx,
                    ds.drawings[_drawSelectedIdx].color || _drawDefaults.color);
            }
        }
    }
    // Brush/Highlighter commit still uses container mouseup
    function brushCommit() {
        if (_drawPending && (_drawPending.type === 'brush' || _drawPending.type === 'highlighter') && _drawPending.chartId === chartId) {
            if (_drawPending.points && _drawPending.points.length > 1) {
                ds.drawings.push(Object.assign({}, _drawPending));
                _drawSelectedIdx = ds.drawings.length - 1;
                _drawSelectedChart = chartId;
                _tvShowFloatingToolbar(chartId, _drawSelectedIdx);
                _emitDrawingAdded(chartId, _drawPending);
            }
            _drawPending = null;
            _tvRenderDrawings(chartId);
        }
    }
    container.addEventListener('mouseup', brushCommit, true);   // capture phase

    // --- Double-click: open drawing settings (cursor mode) ---
    container.addEventListener('dblclick', function(e) {
        if (entry._interactionLocked) return;
        if (ds._activeTool !== 'cursor') return;
        var rect = canvas.getBoundingClientRect();
        var mx = e.clientX - rect.left;
        var my = e.clientY - rect.top;
        var hitIdx = _tvHitTest(chartId, mx, my);
        if (hitIdx >= 0) {
            e.preventDefault();
            e.stopPropagation();
            _drawSelectedIdx = hitIdx;
            _drawSelectedChart = chartId;
            _tvRenderDrawings(chartId);
            _tvShowDrawingSettings(chartId, hitIdx);
        }
    });

    // --- Click: select/deselect drawing (cursor mode) ---
    container.addEventListener('click', function(e) {
        if (entry._interactionLocked) return;
        if (ds._activeTool !== 'cursor') return;
        // Skip click if a drag just completed
        if (_drawDidDrag) {
            _drawDidDrag = false;
            return;
        }
        var rect = canvas.getBoundingClientRect();
        var mx = e.clientX - rect.left;
        var my = e.clientY - rect.top;
        var hitIdx = _tvHitTest(chartId, mx, my);
        if (hitIdx >= 0) {
            _drawSelectedIdx = hitIdx;
            _drawSelectedChart = chartId;
            _tvRenderDrawings(chartId);
            _tvShowFloatingToolbar(chartId, hitIdx);
        } else {
            _tvDeselectAll(chartId);
        }
    });

    // --- Right-click: context menu (cursor mode) ---
    container.addEventListener('contextmenu', function(e) {
        if (entry._interactionLocked) return;
        if (ds._activeTool !== 'cursor') return;
        var rect = canvas.getBoundingClientRect();
        var mx = e.clientX - rect.left;
        var my = e.clientY - rect.top;
        var hitIdx = _tvHitTest(chartId, mx, my);
        if (hitIdx >= 0) {
            e.preventDefault();
            _drawSelectedIdx = hitIdx;
            _drawSelectedChart = chartId;
            _tvRenderDrawings(chartId);
            _tvShowFloatingToolbar(chartId, hitIdx);
            _tvShowContextMenu(chartId, hitIdx, mx, my);
        }
    });

    // =========================================================================
    // Canvas-level listeners: work in DRAWING TOOL mode (canvas has ptr-events:auto)
    // These handle live preview, click-to-place, brush, and drawing-tool context menu.
    // =========================================================================

    // --- Mouse move on canvas: live preview for in-progress drawing ---
    canvas.addEventListener('mousemove', function(e) {
        if (!_drawPending || _drawPending.chartId !== chartId) return;
        var rect = canvas.getBoundingClientRect();
        var mx = e.clientX - rect.left;
        var my = e.clientY - rect.top;
        var pc = _tvFromPixel(chartId, mx, my);
        if (pc) {
            if ((_drawPending.type === 'brush' || _drawPending.type === 'highlighter') && _drawPending.points && !_drawPending._multiPoint) {
                _drawPending.points.push({ t: pc.time, p: pc.price });
            } else if (_drawPending._phase === 2) {
                // 3-point tool: phase 2 previews the third anchor
                _drawPending.t3 = pc.time;
                _drawPending.p3 = pc.price;
            } else {
                _drawPending.t2 = pc.time;
                _drawPending.p2 = pc.price;
            }
            _tvRenderDrawings(chartId);
        }
    });

    // --- Click on canvas: place drawing (drawing tool mode) ---
    canvas.addEventListener('click', function(e) {
        var _tool = ds._activeTool;
        // Drawing tools only — cursor mode is handled on container
        if (_tool === 'cursor' || _tool === 'crosshair') return;

        var rect = canvas.getBoundingClientRect();
        var mx = e.clientX - rect.left;
        var my = e.clientY - rect.top;
        var coord = _tvFromPixel(chartId, mx, my);
        if (!coord || coord.time === null || coord.price === null) return;

        if (_tool === 'hline') {
            var hlD = {
                _id: ++_drawIdCounter, type: 'hline', price: coord.price,
                chartId: chartId, color: _drawDefaults.color,
                lineWidth: _drawDefaults.lineWidth, lineStyle: _drawDefaults.lineStyle,
                showPriceLabel: true, title: '', extend: "Don't extend",
            };
            ds.drawings.push(hlD);
            // Native price line
            var mainKey = Object.keys(entry.seriesMap)[0];
            if (mainKey && entry.seriesMap[mainKey]) {
                var pl = entry.seriesMap[mainKey].createPriceLine({
                    price: coord.price, color: hlD.color,
                    lineWidth: hlD.lineWidth, lineStyle: hlD.lineStyle,
                    axisLabelVisible: true, title: '',
                });
                ds.priceLines.push({ seriesId: mainKey, priceLine: pl });
            }
            _tvRenderDrawings(chartId);
            // Auto-select new drawing
            _drawSelectedIdx = ds.drawings.length - 1;
            _drawSelectedChart = chartId;
            _tvShowFloatingToolbar(chartId, _drawSelectedIdx);
            _emitDrawingAdded(chartId, hlD);
            return;
        }

        if (_tool === 'text') {
            var txtD = {
                _id: ++_drawIdCounter, type: 'text', t1: coord.time, p1: coord.price,
                text: 'Text', chartId: chartId, color: _drawDefaults.color,
                fontSize: 14, lineWidth: _drawDefaults.lineWidth,
            };
            ds.drawings.push(txtD);
            _tvRenderDrawings(chartId);
            _drawSelectedIdx = ds.drawings.length - 1;
            _drawSelectedChart = chartId;
            _tvShowFloatingToolbar(chartId, _drawSelectedIdx);
            _emitDrawingAdded(chartId, txtD);
            // Open settings panel with Text tab
            _tvShowDrawingSettings(chartId, _drawSelectedIdx);
            return;
        }

        // Single-click text/notes tools
        var _singleClickTextTools = ['anchored_text', 'note', 'price_note', 'pin', 'comment', 'price_label', 'signpost', 'flag_mark'];
        if (_singleClickTextTools.indexOf(_tool) !== -1) {
            var _sctDefText = { anchored_text: 'Text', note: 'Note', price_note: 'Price Note', pin: '', comment: 'Comment', price_label: 'Label', signpost: 'Signpost', flag_mark: '' };
            var sctD = {
                _id: ++_drawIdCounter, type: _tool, t1: coord.time, p1: coord.price,
                text: _sctDefText[_tool] || '', chartId: chartId,
                color: _drawDefaults.color, fontSize: 14,
                bold: false, italic: false,
                bgEnabled: true, bgColor: '#2a2e39',
                borderEnabled: false, borderColor: _drawDefaults.color,
                lineWidth: _drawDefaults.lineWidth,
            };
            ds.drawings.push(sctD);
            _tvRenderDrawings(chartId);
            _drawSelectedIdx = ds.drawings.length - 1;
            _drawSelectedChart = chartId;
            _tvShowFloatingToolbar(chartId, _drawSelectedIdx);
            _emitDrawingAdded(chartId, sctD);
            _tvShowDrawingSettings(chartId, _drawSelectedIdx);
            return;
        }

        // Vertical Line — single-click, anchored by time only
        if (_tool === 'vline') {
            var vlD = {
                _id: ++_drawIdCounter, type: 'vline', t1: coord.time,
                chartId: chartId, color: _drawDefaults.color,
                lineWidth: _drawDefaults.lineWidth, lineStyle: _drawDefaults.lineStyle,
            };
            ds.drawings.push(vlD);
            _tvRenderDrawings(chartId);
            _drawSelectedIdx = ds.drawings.length - 1;
            _drawSelectedChart = chartId;
            _tvShowFloatingToolbar(chartId, _drawSelectedIdx);
            _emitDrawingAdded(chartId, vlD);
            return;
        }

        // Cross Line — single-click, crosshair-style
        if (_tool === 'crossline') {
            var clD = {
                _id: ++_drawIdCounter, type: 'crossline', t1: coord.time, p1: coord.price,
                chartId: chartId, color: _drawDefaults.color,
                lineWidth: _drawDefaults.lineWidth, lineStyle: _drawDefaults.lineStyle,
            };
            ds.drawings.push(clD);
            _tvRenderDrawings(chartId);
            _drawSelectedIdx = ds.drawings.length - 1;
            _drawSelectedChart = chartId;
            _tvShowFloatingToolbar(chartId, _drawSelectedIdx);
            _emitDrawingAdded(chartId, clD);
            return;
        }

        // Arrow mark single-click tools
        var arrowMarks = ['arrow_mark_up', 'arrow_mark_down', 'arrow_mark_left', 'arrow_mark_right'];
        if (arrowMarks.indexOf(_tool) !== -1) {
            var amD = {
                _id: ++_drawIdCounter, type: _tool, t1: coord.time, p1: coord.price,
                chartId: chartId, color: _drawDefaults.color,
                fillColor: _drawDefaults.color, borderColor: _drawDefaults.color, textColor: _drawDefaults.color,
                lineWidth: _drawDefaults.lineWidth, size: 30,
                text: '', fontSize: 16, bold: false, italic: false,
            };
            ds.drawings.push(amD);
            _tvRenderDrawings(chartId);
            _drawSelectedIdx = ds.drawings.length - 1;
            _drawSelectedChart = chartId;
            _tvShowFloatingToolbar(chartId, _drawSelectedIdx);
            _emitDrawingAdded(chartId, amD);
            return;
        }

        // Anchored VWAP — single-click anchor point
        if (_tool === 'anchored_vwap') {
            var avD = {
                _id: ++_drawIdCounter, type: 'anchored_vwap', t1: coord.time, p1: coord.price,
                chartId: chartId, color: _drawDefaults.color || '#2962FF',
                lineWidth: _drawDefaults.lineWidth,
            };
            ds.drawings.push(avD);
            _tvRenderDrawings(chartId);
            _drawSelectedIdx = ds.drawings.length - 1;
            _drawSelectedChart = chartId;
            _tvShowFloatingToolbar(chartId, _drawSelectedIdx);
            _emitDrawingAdded(chartId, avD);
            return;
        }

        // Two-point tools (including ray, extended_line, hray, flat_channel, regression_channel)
        var twoPointTools = ['trendline', 'ray', 'extended_line', 'hray',
                             'rect', 'channel', 'flat_channel', 'regression_channel',
                             'fibonacci', 'measure',
                             'fib_timezone', 'fib_fan', 'fib_arc', 'fib_circle',
                             'fib_spiral', 'gann_box', 'gann_square_fixed', 'gann_square', 'gann_fan',
                             'arrow_marker', 'arrow', 'circle', 'ellipse', 'curve',
                             'long_position', 'short_position', 'forecast',
                             'bars_pattern', 'ghost_feed', 'projection', 'fixed_range_vol',
                             'price_range', 'date_range', 'date_price_range',
                             'callout'];
        // Three-point tools (A→B, then C on second click)
        var threePointTools = ['fib_extension', 'fib_channel', 'fib_wedge', 'pitchfan', 'fib_time',
                               'rotated_rect', 'triangle', 'shape_arc', 'double_curve'];
        if (threePointTools.indexOf(_tool) !== -1) {
            if (!_drawPending || _drawPending.chartId !== chartId) {
                // First click: set A
                _drawPending = {
                    _id: ++_drawIdCounter, type: _tool,
                    t1: coord.time, p1: coord.price,
                    t2: coord.time, p2: coord.price,
                    chartId: chartId, color: _drawDefaults.color,
                    lineWidth: _drawDefaults.lineWidth, lineStyle: _drawDefaults.lineStyle,
                    _phase: 1,
                };
            } else if (_drawPending._phase === 1) {
                // Second click: set B, start previewing C
                _drawPending.t2 = coord.time;
                _drawPending.p2 = coord.price;
                _drawPending.t3 = coord.time;
                _drawPending.p3 = coord.price;
                _drawPending._phase = 2;
            } else {
                // Third click: set C, commit
                _drawPending.t3 = coord.time;
                _drawPending.p3 = coord.price;
                delete _drawPending._phase;
                ds.drawings.push(Object.assign({}, _drawPending));
                var committed = _drawPending;
                _drawPending = null;
                _tvRenderDrawings(chartId);
                _drawSelectedIdx = ds.drawings.length - 1;
                _drawSelectedChart = chartId;
                _tvShowFloatingToolbar(chartId, _drawSelectedIdx);
                _emitDrawingAdded(chartId, committed);
            }
            return;
        }
        if (twoPointTools.indexOf(_tool) !== -1) {
            if (!_drawPending || _drawPending.chartId !== chartId) {
                _drawPending = {
                    _id: ++_drawIdCounter, type: _tool,
                    t1: coord.time, p1: coord.price,
                    t2: coord.time, p2: coord.price,
                    chartId: chartId, color: _drawDefaults.color,
                    lineWidth: _drawDefaults.lineWidth, lineStyle: _drawDefaults.lineStyle,
                    offset: 30,
                    extend: "Don't extend",
                    ray: false,
                    showMiddlePoint: false,
                    showPriceLabels: false,
                    stats: 'hidden',
                    statsPosition: 'right',
                    alwaysShowStats: false,
                };
                if (_tool === 'arrow_marker' || _tool === 'arrow') {
                    _drawPending.text = '';
                    _drawPending.fontSize = 16;
                    _drawPending.bold = false;
                    _drawPending.italic = false;
                    _drawPending.fillColor = _drawDefaults.color;
                    _drawPending.borderColor = _drawDefaults.color;
                    _drawPending.textColor = _drawDefaults.color;
                }
                if (_tool === 'callout') {
                    _drawPending.text = 'Callout';
                    _drawPending.fontSize = 14;
                    _drawPending.bold = false;
                    _drawPending.italic = false;
                    _drawPending.bgEnabled = true;
                    _drawPending.bgColor = '#2a2e39';
                    _drawPending.borderEnabled = false;
                    _drawPending.borderColor = _drawDefaults.color;
                }
            } else {
                _drawPending.t2 = coord.time;
                _drawPending.p2 = coord.price;
                ds.drawings.push(Object.assign({}, _drawPending));
                var committed = _drawPending;
                _drawPending = null;
                _tvRenderDrawings(chartId);
                // Auto-select
                _drawSelectedIdx = ds.drawings.length - 1;
                _drawSelectedChart = chartId;
                _tvShowFloatingToolbar(chartId, _drawSelectedIdx);
                _emitDrawingAdded(chartId, committed);
            }
            return;
        }

        // Brush / Highlighter — free-form drawing, collect points on drag
        if (_tool === 'brush' || _tool === 'highlighter') {
            _drawPending = {
                _id: ++_drawIdCounter, type: _tool,
                points: [{ t: coord.time, p: coord.price }],
                chartId: chartId, color: _drawDefaults.color,
                lineWidth: _tool === 'highlighter' ? 10 : _drawDefaults.lineWidth,
                opacity: _tool === 'highlighter' ? 0.4 : 1,
            };
            _tvRenderDrawings(chartId);
            return;
        }

        // Path / Polyline — click-per-point, double-click or right-click to finish
        if (_tool === 'path' || _tool === 'polyline') {
            if (!_drawPending || _drawPending.chartId !== chartId) {
                _drawPending = {
                    _id: ++_drawIdCounter, type: _tool,
                    points: [{ t: coord.time, p: coord.price }],
                    chartId: chartId, color: _drawDefaults.color,
                    lineWidth: _drawDefaults.lineWidth, lineStyle: _drawDefaults.lineStyle,
                    _multiPoint: true,
                };
            } else {
                _drawPending.points.push({ t: coord.time, p: coord.price });
            }
            _tvRenderDrawings(chartId);
            return;
        }
    });

    // Double-click to commit path/polyline
    canvas.addEventListener('dblclick', function(e) {
        if (!_drawPending || !_drawPending._multiPoint) return;
        var d = _drawPending;
        // Remove last duplicated point from dblclick
        if (d.points.length > 2) d.points.pop();
        delete d._multiPoint;
        ds.drawings.push(Object.assign({}, d));
        var committed = d;
        _drawPending = null;
        _tvRenderDrawings(chartId);
        _drawSelectedIdx = ds.drawings.length - 1;
        _drawSelectedChart = chartId;
        _tvShowFloatingToolbar(chartId, _drawSelectedIdx);
        _emitDrawingAdded(chartId, committed);
    });

    // --- Right-click on canvas: cancel pending drawing and revert to cursor ---
    canvas.addEventListener('contextmenu', function(e) {
        if (_drawPending) {
            e.preventDefault();
            _drawPending = null;
            _tvRenderDrawings(chartId);
            _tvRevertToCursor(chartId);
        } else if (ds._activeTool !== 'cursor' && ds._activeTool !== 'crosshair') {
            e.preventDefault();
            _tvRevertToCursor(chartId);
        }
    });

    // --- Keyboard shortcuts ---
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            // Cancel pending drawing
            if (_drawPending) {
                _drawPending = null;
                _tvRenderDrawings(chartId);
            }
            // If a drawing tool is active, revert to cursor
            if (ds._activeTool !== 'cursor' && ds._activeTool !== 'crosshair') {
                _tvRevertToCursor(chartId);
                return;
            }
            // Otherwise deselect any selected drawing
            if (_drawSelectedIdx >= 0 && _drawSelectedChart === chartId) {
                _tvDeselectAll(chartId);
            }
            return;
        }
        if (_drawSelectedIdx < 0 || _drawSelectedChart !== chartId) return;
        if (e.key === 'Delete' || e.key === 'Backspace') {
            e.preventDefault();
            _tvDeleteDrawing(chartId, _drawSelectedIdx);
        }
    });
}

function _tvDeselectAll(chartId) {
    _drawSelectedIdx   = -1;
    _drawSelectedChart = null;
    _drawHoverIdx      = -1;
    _tvHideFloatingToolbar();
    _tvHideContextMenu();
    _tvRenderDrawings(chartId);
}

// Revert to cursor mode and update the left toolbar UI
function _tvRevertToCursor(chartId) {
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds || ds._activeTool === 'cursor') return;
    _tvSetDrawTool(chartId, 'cursor');
    // Update left toolbar scoped to this chart
    var allIcons = _tvScopedQueryAll(chartId, '.pywry-toolbar-left .pywry-icon-btn');
    if (allIcons) allIcons.forEach(function(el) { el.classList.remove('active'); });
    var cursorBtn = _tvScopedById(chartId, 'tvchart-tool-cursor');
    if (cursorBtn) cursorBtn.classList.add('active');
}

function _emitDrawingAdded(chartId, d) {
    // Push undo entry for the newly added drawing (always the last in the array)
    var _undoChartId = chartId;
    var _undoDrawing = Object.assign({}, d);
    _tvPushUndo({
        label: 'Add ' + (d.type || 'drawing'),
        undo: function() {
            var ds = window.__PYWRY_DRAWINGS__[_undoChartId];
            if (!ds) return;
            // Find and remove the drawing by _id
            for (var i = ds.drawings.length - 1; i >= 0; i--) {
                if (ds.drawings[i]._id === _undoDrawing._id) {
                    // Remove native price line if hline
                    if (ds.drawings[i].type === 'hline' && ds.priceLines[i]) {
                        var entry = window.__PYWRY_TVCHARTS__[_undoChartId];
                        if (entry) {
                            var pl = ds.priceLines[i];
                            var ser = entry.seriesMap[pl.seriesId];
                            if (ser) try { ser.removePriceLine(pl.priceLine); } catch(e) {}
                        }
                        ds.priceLines.splice(i, 1);
                    }
                    ds.drawings.splice(i, 1);
                    break;
                }
            }
            _tvDeselectAll(_undoChartId);
        },
        redo: function() {
            var ds = window.__PYWRY_DRAWINGS__[_undoChartId];
            if (!ds) return;
            ds.drawings.push(Object.assign({}, _undoDrawing));
            // Re-create native price line if hline
            if (_undoDrawing.type === 'hline') {
                var entry = window.__PYWRY_TVCHARTS__[_undoChartId];
                if (entry) {
                    var mainKey = Object.keys(entry.seriesMap)[0];
                    if (mainKey && entry.seriesMap[mainKey]) {
                        var pl = entry.seriesMap[mainKey].createPriceLine({
                            price: _undoDrawing.price, color: _undoDrawing.color,
                            lineWidth: _undoDrawing.lineWidth, lineStyle: _undoDrawing.lineStyle,
                            axisLabelVisible: true, title: '',
                        });
                        ds.priceLines.push({ seriesId: mainKey, priceLine: pl });
                    }
                }
            }
            _tvDeselectAll(_undoChartId);
        },
    });
    if (window.pywry && window.pywry.emit) {
        window.pywry.emit('tvchart:drawing-added', { chartId: chartId, drawing: d });
    }
    // Auto-revert to cursor after every drawing finishes so the
    // toolbar button doesn't stay highlighted forever.
    _tvRevertToCursor(chartId);
}

// ---- Tool switching ----
function _tvSetDrawTool(chartId, tool) {
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds) {
        _tvEnsureDrawingLayer(chartId);
        ds = window.__PYWRY_DRAWINGS__[chartId];
    }
    if (!ds) return;

    ds._activeTool = tool;
    if (_drawPending && _drawPending.chartId === chartId) {
        _drawPending = null;
    }

    _tvApplyDrawingInteractionMode(ds);

    // Toggle chart crosshair lines based on tool selection
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (entry && entry._chartPrefs) {
        entry._chartPrefs.crosshairEnabled = (tool === 'crosshair');
        _tvApplyHoverReadoutMode(entry);
    }

    // Deselect when switching tools
    _tvDeselectAll(chartId);
}

// ---- Clear all drawings ----
function _tvClearDrawings(chartId) {
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds) return;
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (entry) {
        for (var i = 0; i < ds.priceLines.length; i++) {
            var pl = ds.priceLines[i];
            var ser = entry.seriesMap[pl.seriesId];
            if (ser) try { ser.removePriceLine(pl.priceLine); } catch(e) {}
        }
    }
    ds.priceLines = [];
    ds.drawings   = [];
    if (_drawPending && _drawPending.chartId === chartId) _drawPending = null;
    _drawSelectedIdx   = -1;
    _drawSelectedChart = null;
    _tvHideFloatingToolbar();
    _tvHideContextMenu();
    _tvRenderDrawings(chartId);
}

