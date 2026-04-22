function _tvDrawOne(ctx, d, chartId, defColor, textColor, w, h, selected, hovered, mouseOver, viewport) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry) return;
    var series = _tvMainSeries(chartId);
    if (!series) return;
    viewport = viewport || _tvGetDrawingViewport(chartId);

    var col = d.color || defColor;
    var lw  = d.lineWidth || 2;
    if (hovered) { lw += 0.5; }

    ctx.save();
    ctx.strokeStyle = col;
    ctx.fillStyle   = col;
    ctx.lineWidth   = lw;
    ctx.lineJoin    = 'round';
    ctx.lineCap     = 'round';
    ctx.beginPath();
    ctx.rect(viewport.left, viewport.top, viewport.width, viewport.height);
    ctx.clip();

    // Line style
    if (d.lineStyle === 1) ctx.setLineDash([6, 4]);
    else if (d.lineStyle === 2) ctx.setLineDash([2, 3]);
    else ctx.setLineDash([]);

    // Pre-compute common anchor pixel positions used by many drawing types
    var p1 = (d.t1 !== undefined && d.p1 !== undefined) ? _tvToPixel(chartId, d.t1, d.p1) : null;
    var p2 = (d.t2 !== undefined && d.p2 !== undefined) ? _tvToPixel(chartId, d.t2, d.p2) : null;

    if (d.type === 'hline') {
        var yH = series.priceToCoordinate(d.price);
        if (yH !== null) {
            ctx.beginPath();
            ctx.moveTo(0, yH);
            ctx.lineTo(w, yH);
            ctx.stroke();
            // Canvas price-label box (supplements the native price-line label).
            // Only drawn when showPriceLabel is not explicitly false.
            if (d.showPriceLabel !== false) {
                var labelBoxColor = d.labelColor || col;
                var prLabel = (d.title ? d.title + ' ' : '') + Number(d.price).toFixed(2);
                ctx.font = 'bold 11px -apple-system,BlinkMacSystemFont,sans-serif';
                var pm = ctx.measureText(prLabel);
                var plw = pm.width + 10;
                var plh = 20;
                var plx = viewport.right - plw - 4;
                var ply = yH - plh / 2;
                ctx.fillStyle = labelBoxColor;
                ctx.beginPath();
                var r = 3;
                ctx.moveTo(plx + r, ply);
                ctx.lineTo(plx + plw - r, ply);
                ctx.quadraticCurveTo(plx + plw, ply, plx + plw, ply + r);
                ctx.lineTo(plx + plw, ply + plh - r);
                ctx.quadraticCurveTo(plx + plw, ply + plh, plx + plw - r, ply + plh);
                ctx.lineTo(plx + r, ply + plh);
                ctx.quadraticCurveTo(plx, ply + plh, plx, ply + plh - r);
                ctx.lineTo(plx, ply + r);
                ctx.quadraticCurveTo(plx, ply, plx + r, ply);
                ctx.fill();
                ctx.fillStyle = _cssVar('--pywry-draw-label-text');
                ctx.textBaseline = 'middle';
                ctx.fillText(prLabel, plx + 5, yH);
                ctx.textBaseline = 'alphabetic';
            }
        }
    } else if (d.type === 'trendline') {
        var a = _tvToPixel(chartId, d.t1, d.p1);
        var b = _tvToPixel(chartId, d.t2, d.p2);
        if (a && b) {
            var dx = b.x - a.x, dy = b.y - a.y;
            var len = Math.sqrt(dx * dx + dy * dy);
            if (len > 0) {
                var ext = 4000;
                var ux = dx / len, uy = dy / len;
                var startX = a.x, startY = a.y;
                var endX = b.x, endY = b.y;
                var extMode = d.extend || "Don't extend";
                if (d.ray) {
                    // Ray mode: start at A, extend through B to infinity
                    endX = b.x + ux * ext;
                    endY = b.y + uy * ext;
                } else if (extMode === 'Left' || extMode === 'Both') {
                    startX = a.x - ux * ext;
                    startY = a.y - uy * ext;
                }
                if (!d.ray && (extMode === 'Right' || extMode === 'Both')) {
                    endX = b.x + ux * ext;
                    endY = b.y + uy * ext;
                }
                ctx.beginPath();
                ctx.moveTo(startX, startY);
                ctx.lineTo(endX, endY);
                ctx.stroke();
            }
            // Middle point
            if (d.showMiddlePoint) {
                var midX = (a.x + b.x) / 2, midY = (a.y + b.y) / 2;
                ctx.beginPath();
                ctx.arc(midX, midY, 4, 0, Math.PI * 2);
                ctx.fillStyle = col;
                ctx.fill();
            }
            // Price labels at endpoints
            if (d.showPriceLabels) {
                ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                ctx.fillStyle = col;
                var p1Txt = d.p1 !== undefined ? d.p1.toFixed(2) : '';
                var p2Txt = d.p2 !== undefined ? d.p2.toFixed(2) : '';
                ctx.fillText(p1Txt, a.x + 4, a.y - 6);
                ctx.fillText(p2Txt, b.x + 4, b.y - 6);
            }
            // Text annotation (from Text tab in settings)
            if (d.text) {
                var tMidX = (a.x + b.x) / 2, tMidY = (a.y + b.y) / 2;
                var tFs = d.textFontSize || 12;
                var tStyle = (d.textItalic ? 'italic ' : '') + (d.textBold ? 'bold ' : '');
                ctx.font = tStyle + tFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
                ctx.fillStyle = d.textColor || col;
                ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
                ctx.fillText(d.text, tMidX, tMidY - 6);
                ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
            }
            // Stats (from Inputs tab: hidden/compact/values)
            if (d.stats && d.stats !== 'hidden' && a && b) {
                var sDx = d.p2 - d.p1, sPct = d.p1 !== 0 ? ((sDx / d.p1) * 100) : 0;
                var sBars = Math.abs(Math.round((d.t2 - d.t1) / 86400)); // approximate bar count
                var sText = '';
                if (d.stats === 'compact') {
                    sText = (sDx >= 0 ? '+' : '') + sDx.toFixed(2) + ' (' + (sPct >= 0 ? '+' : '') + sPct.toFixed(2) + '%)';
                } else {
                    sText = (sDx >= 0 ? '+' : '') + sDx.toFixed(2) + ' (' + (sPct >= 0 ? '+' : '') + sPct.toFixed(2) + '%)' + ' | ' + sBars + ' bars';
                }
                var sFs = 11;
                ctx.font = sFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
                ctx.fillStyle = col;
                var sAnchor = d.statsPosition === 'left' ? a : b;
                var sAlign = d.statsPosition === 'left' ? 'left' : 'right';
                ctx.textAlign = sAlign; ctx.textBaseline = 'top';
                ctx.fillText(sText, sAnchor.x, sAnchor.y + 6);
                ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
            }
        }
    } else if (d.type === 'rect') {
        var r1 = _tvToPixel(chartId, d.t1, d.p1);
        var r2 = _tvToPixel(chartId, d.t2, d.p2);
        if (r1 && r2) {
            var rx = Math.min(r1.x, r2.x), ry = Math.min(r1.y, r2.y);
            var rw = Math.abs(r2.x - r1.x), rh = Math.abs(r2.y - r1.y);
            if (d.fillEnabled !== false) {
                ctx.fillStyle = d.fillColor || col;
                ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.15;
                ctx.fillRect(rx, ry, rw, rh);
                ctx.globalAlpha = 1.0;
            }
            ctx.strokeRect(rx, ry, rw, rh);
        }
    } else if (d.type === 'text') {
        var tp = _tvToPixel(chartId, d.t1, d.p1);
        if (tp) {
            var fontStyle = (d.italic ? 'italic ' : '') + (d.bold !== false ? 'bold ' : '');
            ctx.font = fontStyle + (d.fontSize || 14) + 'px -apple-system,BlinkMacSystemFont,sans-serif';
            var textContent = d.text || 'Text';
            if (d.bgEnabled) {
                var tm = ctx.measureText(textContent);
                var pad = 4;
                ctx.fillStyle = d.bgColor || _cssVar('--pywry-draw-text-bg');
                ctx.globalAlpha = d.bgOpacity !== undefined ? d.bgOpacity : 0.7;
                ctx.fillRect(tp.x - pad, tp.y - (d.fontSize || 14) - pad, tm.width + pad * 2, (d.fontSize || 14) + pad * 2);
                ctx.globalAlpha = 1.0;
            }
            ctx.fillStyle = d.color || defColor;
            ctx.fillText(textContent, tp.x, tp.y);
        }
    } else if (d.type === 'anchored_text') {
        // Anchored Text: text with a dot anchor below
        var atp = _tvToPixel(chartId, d.t1, d.p1);
        if (atp) {
            var _atFs = d.fontSize || 14;
            var _atFw = (d.italic ? 'italic ' : '') + (d.bold ? 'bold ' : '');
            ctx.font = _atFw + _atFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
            var _atTxt = d.text || 'Text';
            var _atTm = ctx.measureText(_atTxt);
            if (d.bgEnabled) {
                var _atPad = 4;
                ctx.fillStyle = d.bgColor || '#2a2e39';
                ctx.globalAlpha = 0.7;
                ctx.fillRect(atp.x - _atTm.width / 2 - _atPad, atp.y - _atFs - _atPad, _atTm.width + _atPad * 2, _atFs + _atPad * 2);
                ctx.globalAlpha = 1.0;
            }
            ctx.fillStyle = d.color || defColor;
            ctx.textAlign = 'center';
            ctx.fillText(_atTxt, atp.x, atp.y);
            // Anchor dot
            ctx.beginPath();
            ctx.arc(atp.x, atp.y + 6, 3, 0, Math.PI * 2);
            ctx.fill();
            ctx.textAlign = 'start';
        }
    } else if (d.type === 'note') {
        // Note: text block with border
        var ntp = _tvToPixel(chartId, d.t1, d.p1);
        if (ntp) {
            var _nFs = d.fontSize || 14;
            var _nFw = (d.italic ? 'italic ' : '') + (d.bold ? 'bold ' : '');
            ctx.font = _nFw + _nFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
            var _nTxt = d.text || 'Note';
            var _nTm = ctx.measureText(_nTxt);
            var _nPad = 8;
            var _nW = _nTm.width + _nPad * 2;
            var _nH = _nFs + _nPad * 2;
            if (d.bgEnabled !== false) {
                ctx.fillStyle = d.bgColor || '#2a2e39';
                ctx.globalAlpha = 0.85;
                ctx.fillRect(ntp.x, ntp.y - _nH, _nW, _nH);
                ctx.globalAlpha = 1.0;
            }
            if (d.borderEnabled) {
                ctx.strokeStyle = d.borderColor || col;
                ctx.strokeRect(ntp.x, ntp.y - _nH, _nW, _nH);
                ctx.strokeStyle = col;
            }
            ctx.fillStyle = d.color || defColor;
            ctx.fillText(_nTxt, ntp.x + _nPad, ntp.y - _nPad);
        }
    } else if (d.type === 'price_note') {
        // Price Note: note anchored to a price level with horizontal dash
        var pnp = _tvToPixel(chartId, d.t1, d.p1);
        if (pnp) {
            var _pnFs = d.fontSize || 14;
            var _pnFw = (d.italic ? 'italic ' : '') + (d.bold ? 'bold ' : '');
            ctx.font = _pnFw + _pnFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
            var _pnTxt = d.text || 'Price Note';
            var _pnTm = ctx.measureText(_pnTxt);
            var _pnPad = 6;
            var _pnW = _pnTm.width + _pnPad * 2;
            var _pnH = _pnFs + _pnPad * 2;
            // Horizontal price dash
            ctx.setLineDash([4, 3]);
            ctx.beginPath();
            ctx.moveTo(pnp.x + _pnW + 4, pnp.y - _pnH / 2);
            ctx.lineTo(pnp.x + _pnW + 40, pnp.y - _pnH / 2);
            ctx.stroke();
            ctx.setLineDash(ls);
            if (d.bgEnabled !== false) {
                ctx.fillStyle = d.bgColor || '#2a2e39';
                ctx.globalAlpha = 0.85;
                ctx.fillRect(pnp.x, pnp.y - _pnH, _pnW, _pnH);
                ctx.globalAlpha = 1.0;
            }
            if (d.borderEnabled) {
                ctx.strokeStyle = d.borderColor || col;
                ctx.strokeRect(pnp.x, pnp.y - _pnH, _pnW, _pnH);
                ctx.strokeStyle = col;
            }
            ctx.fillStyle = d.color || defColor;
            ctx.fillText(_pnTxt, pnp.x + _pnPad, pnp.y - _pnPad);
        }
    } else if (d.type === 'pin') {
        // Pin: map-pin icon with text bubble above
        var pinP = _tvToPixel(chartId, d.t1, d.p1);
        if (pinP) {
            var pinCol = d.markerColor || col;
            // Draw pin marker (teardrop shape)
            var pinR = 8;
            ctx.beginPath();
            ctx.arc(pinP.x, pinP.y - pinR - 6, pinR, Math.PI, 0, false);
            ctx.lineTo(pinP.x, pinP.y);
            ctx.closePath();
            ctx.fillStyle = pinCol;
            ctx.fill();
            // Inner dot
            ctx.beginPath();
            ctx.arc(pinP.x, pinP.y - pinR - 6, 3, 0, Math.PI * 2);
            ctx.fillStyle = '#1e222d';
            ctx.fill();
            // Text bubble if text present (mouseover only)
            if (d.text && mouseOver) {
                var _pinFs = d.fontSize || 14;
                var _pinFw = (d.italic ? 'italic ' : '') + (d.bold ? 'bold ' : '');
                ctx.font = _pinFw + _pinFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
                var _pinTm = ctx.measureText(d.text);
                var _pinPad = 8;
                var _pinBW = _pinTm.width + _pinPad * 2;
                var _pinBH = _pinFs + _pinPad * 2;
                var _pinBY = pinP.y - pinR * 2 - 12 - _pinBH;
                var _pinBX = pinP.x - _pinBW / 2;
                // Bubble background
                ctx.fillStyle = d.bgColor || '#3a3e4a';
                ctx.globalAlpha = 0.9;
                _tvRoundRect(ctx, _pinBX, _pinBY, _pinBW, _pinBH, 4);
                ctx.fill();
                ctx.globalAlpha = 1.0;
                // Bubble pointer
                ctx.beginPath();
                ctx.moveTo(pinP.x - 5, _pinBY + _pinBH);
                ctx.lineTo(pinP.x, _pinBY + _pinBH + 6);
                ctx.lineTo(pinP.x + 5, _pinBY + _pinBH);
                ctx.fillStyle = d.bgColor || '#3a3e4a';
                ctx.fill();
                // Text
                ctx.fillStyle = d.color || defColor;
                ctx.textAlign = 'center';
                ctx.fillText(d.text, pinP.x, _pinBY + _pinBH - _pinPad);
                ctx.textAlign = 'start';
            }
            // Small anchor circle at bottom
            ctx.beginPath();
            ctx.arc(pinP.x, pinP.y + 3, 2, 0, Math.PI * 2);
            ctx.fillStyle = pinCol;
            ctx.fill();
        }
    } else if (d.type === 'callout') {
        // Callout: speech bubble with pointer from p2 to p1
        var clP1 = _tvToPixel(chartId, d.t1, d.p1);
        var clP2 = d.t2 !== undefined ? _tvToPixel(chartId, d.t2, d.p2) : null;
        if (clP1) {
            var _clFs = d.fontSize || 14;
            var _clFw = (d.italic ? 'italic ' : '') + (d.bold ? 'bold ' : '');
            ctx.font = _clFw + _clFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
            var _clTxt = d.text || 'Callout';
            var _clTm = ctx.measureText(_clTxt);
            var _clPad = 10;
            var _clW = _clTm.width + _clPad * 2;
            var _clH = _clFs + _clPad * 2;
            var _clX = clP1.x;
            var _clY = clP1.y - _clH;
            // Background
            ctx.fillStyle = d.bgColor || '#2a2e39';
            ctx.globalAlpha = 0.9;
            _tvRoundRect(ctx, _clX, _clY, _clW, _clH, 4);
            ctx.fill();
            ctx.globalAlpha = 1.0;
            if (d.borderEnabled) {
                ctx.strokeStyle = d.borderColor || col;
                _tvRoundRect(ctx, _clX, _clY, _clW, _clH, 4);
                ctx.stroke();
                ctx.strokeStyle = col;
            }
            // Pointer line to p2
            if (clP2) {
                ctx.beginPath();
                ctx.moveTo(_clX + _clW / 2, clP1.y);
                ctx.lineTo(clP2.x, clP2.y);
                ctx.stroke();
            }
            // Text
            ctx.fillStyle = d.color || defColor;
            ctx.fillText(_clTxt, _clX + _clPad, clP1.y - _clPad);
        }
    } else if (d.type === 'comment') {
        // Comment: circular bubble with text
        var cmP = _tvToPixel(chartId, d.t1, d.p1);
        if (cmP) {
            var _cmFs = d.fontSize || 14;
            var _cmFw = (d.italic ? 'italic ' : '') + (d.bold ? 'bold ' : '');
            ctx.font = _cmFw + _cmFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
            var _cmTxt = d.text || 'Comment';
            var _cmTm = ctx.measureText(_cmTxt);
            var _cmR = Math.max(_cmTm.width / 2 + 12, _cmFs + 8);
            // Background circle
            ctx.beginPath();
            ctx.arc(cmP.x, cmP.y - _cmR, _cmR, 0, Math.PI * 2);
            ctx.fillStyle = d.bgColor || '#2a2e39';
            ctx.globalAlpha = 0.85;
            ctx.fill();
            ctx.globalAlpha = 1.0;
            ctx.strokeStyle = d.borderEnabled ? (d.borderColor || col) : col;
            ctx.stroke();
            ctx.strokeStyle = col;
            // Pointer triangle
            ctx.beginPath();
            ctx.moveTo(cmP.x - 5, cmP.y - 2);
            ctx.lineTo(cmP.x, cmP.y + 6);
            ctx.lineTo(cmP.x + 5, cmP.y - 2);
            ctx.fillStyle = d.bgColor || '#2a2e39';
            ctx.fill();
            // Text
            ctx.fillStyle = d.color || defColor;
            ctx.textAlign = 'center';
            ctx.fillText(_cmTxt, cmP.x, cmP.y - _cmR + 4);
            ctx.textAlign = 'start';
        }
    } else if (d.type === 'price_label') {
        // Price Label: arrow-shaped label pointing right
        var plP = _tvToPixel(chartId, d.t1, d.p1);
        if (plP) {
            var _plFs = d.fontSize || 14;
            var _plFw = (d.italic ? 'italic ' : '') + (d.bold ? 'bold ' : '');
            ctx.font = _plFw + _plFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
            var _plTxt = d.text || 'Label';
            var _plTm = ctx.measureText(_plTxt);
            var _plPad = 6;
            var _plW = _plTm.width + _plPad * 2;
            var _plH = _plFs + _plPad * 2;
            var _plArr = 8;
            // Arrow-shaped polygon
            ctx.beginPath();
            ctx.moveTo(plP.x, plP.y - _plH / 2);
            ctx.lineTo(plP.x + _plW, plP.y - _plH / 2);
            ctx.lineTo(plP.x + _plW + _plArr, plP.y);
            ctx.lineTo(plP.x + _plW, plP.y + _plH / 2);
            ctx.lineTo(plP.x, plP.y + _plH / 2);
            ctx.closePath();
            ctx.fillStyle = d.bgColor || col;
            ctx.globalAlpha = 0.85;
            ctx.fill();
            ctx.globalAlpha = 1.0;
            ctx.stroke();
            // Text
            ctx.fillStyle = d.color || '#ffffff';
            ctx.textAlign = 'left';
            ctx.textBaseline = 'middle';
            ctx.fillText(_plTxt, plP.x + _plPad, plP.y);
            ctx.textBaseline = 'alphabetic';
        }
    } else if (d.type === 'signpost') {
        // Signpost: vertical pole with flag-like sign
        var spP = _tvToPixel(chartId, d.t1, d.p1);
        if (spP) {
            var spCol = d.markerColor || col;
            var _spFs = d.fontSize || 14;
            var _spFw = (d.italic ? 'italic ' : '') + (d.bold ? 'bold ' : '');
            ctx.font = _spFw + _spFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
            var _spTxt = d.text || 'Signpost';
            var _spTm = ctx.measureText(_spTxt);
            var _spPad = 6;
            var _spW = _spTm.width + _spPad * 2;
            var _spH = _spFs + _spPad * 2;
            // Vertical pole
            ctx.beginPath();
            ctx.moveTo(spP.x, spP.y);
            ctx.lineTo(spP.x, spP.y - _spH - 20);
            ctx.strokeStyle = spCol;
            ctx.stroke();
            // Sign shape (flag)
            ctx.beginPath();
            ctx.moveTo(spP.x, spP.y - _spH - 20);
            ctx.lineTo(spP.x + _spW, spP.y - _spH - 16);
            ctx.lineTo(spP.x + _spW, spP.y - 24);
            ctx.lineTo(spP.x, spP.y - 20);
            ctx.closePath();
            ctx.fillStyle = d.bgColor || spCol;
            ctx.globalAlpha = 0.85;
            ctx.fill();
            ctx.globalAlpha = 1.0;
            if (d.borderEnabled) {
                ctx.stroke();
            }
            // Text on sign
            ctx.fillStyle = d.color || '#ffffff';
            ctx.textBaseline = 'middle';
            ctx.fillText(_spTxt, spP.x + _spPad, spP.y - _spH / 2 - 20);
            ctx.textBaseline = 'alphabetic';
        }
    } else if (d.type === 'flag_mark') {
        // Flag Mark: small flag on a pole
        var fmP = _tvToPixel(chartId, d.t1, d.p1);
        if (fmP) {
            var fmCol = d.markerColor || col;
            var _fmFs = d.fontSize || 14;
            // Pole
            ctx.beginPath();
            ctx.moveTo(fmP.x, fmP.y);
            ctx.lineTo(fmP.x, fmP.y - 30);
            ctx.strokeStyle = fmCol;
            ctx.stroke();
            // Flag
            ctx.beginPath();
            ctx.moveTo(fmP.x, fmP.y - 30);
            ctx.lineTo(fmP.x + 20, fmP.y - 26);
            ctx.lineTo(fmP.x + 16, fmP.y - 22);
            ctx.lineTo(fmP.x + 20, fmP.y - 18);
            ctx.lineTo(fmP.x, fmP.y - 18);
            ctx.closePath();
            ctx.fillStyle = fmCol;
            ctx.fill();
            // Text below (mouseover only)
            if (d.text && mouseOver) {
                var _fmFw = (d.italic ? 'italic ' : '') + (d.bold ? 'bold ' : '');
                ctx.font = _fmFw + _fmFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
                ctx.fillStyle = d.color || defColor;
                ctx.textAlign = 'center';
                ctx.fillText(d.text, fmP.x, fmP.y + _fmFs + 4);
                ctx.textAlign = 'start';
            }
        }
    } else if (d.type === 'channel') {
        var c1 = _tvToPixel(chartId, d.t1, d.p1);
        var c2 = _tvToPixel(chartId, d.t2, d.p2);
        if (c1 && c2) {
            var chanOff = d.offset || 30;
            // Fill between lines
            if (d.fillEnabled !== false) {
                ctx.fillStyle = d.fillColor || col;
                ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.08;
                ctx.beginPath();
                ctx.moveTo(c1.x, c1.y);
                ctx.lineTo(c2.x, c2.y);
                ctx.lineTo(c2.x, c2.y + chanOff);
                ctx.lineTo(c1.x, c1.y + chanOff);
                ctx.closePath();
                ctx.fill();
                ctx.globalAlpha = 1.0;
            }
            // Main line
            ctx.beginPath();
            ctx.moveTo(c1.x, c1.y);
            ctx.lineTo(c2.x, c2.y);
            ctx.stroke();
            // Parallel line
            ctx.beginPath();
            ctx.moveTo(c1.x, c1.y + chanOff);
            ctx.lineTo(c2.x, c2.y + chanOff);
            ctx.stroke();
            // Middle dashed line
            if (d.showMiddleLine !== false) {
                ctx.setLineDash([4, 4]);
                ctx.globalAlpha = 0.5;
                ctx.beginPath();
                ctx.moveTo(c1.x, c1.y + chanOff / 2);
                ctx.lineTo(c2.x, c2.y + chanOff / 2);
                ctx.stroke();
                ctx.globalAlpha = 1.0;
            }
            ctx.setLineDash(d.lineStyle === 1 ? [6,4] : d.lineStyle === 2 ? [2,3] : []);
        }
    } else if (d.type === 'fibonacci') {
        var fTop = series.priceToCoordinate(d.p1);
        var fBot = series.priceToCoordinate(d.p2);
        if (fTop !== null && fBot !== null) {
            // Reverse swaps the direction of level interpolation
            var fibAnchorTop = d.reverse ? fBot : fTop;
            var fibAnchorBot = d.reverse ? fTop : fBot;
            var fibPriceTop = d.reverse ? d.p2 : d.p1;
            var fibPriceBot = d.reverse ? d.p1 : d.p2;
            var fibLevels = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : _FIB_LEVELS.slice();
            var fibColors = (d.fibColors && d.fibColors.length) ? d.fibColors : _getFibColors();
            var fibEnabled = d.fibEnabled || [];
            var showLbls = d.showLabels !== false;
            var showPrices = d.showPrices !== false;
            // Use user-set lineStyle; endpoints always solid
            var fibDash = d.lineStyle === 1 ? [6, 4] : d.lineStyle === 2 ? [2, 3] : [4, 3];
            for (var fi = 0; fi < fibLevels.length; fi++) {
                if (fibEnabled[fi] === false) continue;
                var lvl = fibEnabled.length ? fibLevels[fi] : _FIB_LEVELS[fi];
                var yFib = fibAnchorTop + (fibAnchorBot - fibAnchorTop) * lvl;
                var fc = fibColors[fi] || col;
                // Zone fill between this level and next
                if (fi < fibLevels.length - 1 && fibEnabled[fi + 1] !== false) {
                    var yNext = fibAnchorTop + (fibAnchorBot - fibAnchorTop) * fibLevels[fi + 1];
                    ctx.fillStyle = fc;
                    ctx.globalAlpha = 0.06;
                    ctx.fillRect(0, Math.min(yFib, yNext), w, Math.abs(yNext - yFib));
                    ctx.globalAlpha = 1.0;
                }
                // Level line — respect user lineStyle and lineWidth
                ctx.strokeStyle = fc;
                ctx.lineWidth = lvl === 0 || lvl === 1 ? lw : Math.max(1, lw - 1);
                ctx.setLineDash(lvl === 0 || lvl === 1 ? [] : fibDash);
                ctx.beginPath();
                ctx.moveTo(0, yFib);
                ctx.lineTo(w, yFib);
                ctx.stroke();
                // Label
                if (showLbls || showPrices) {
                    var priceFib = fibPriceTop + (fibPriceBot - fibPriceTop) * lvl;
                    ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                    ctx.fillStyle = fc;
                    var fibLabel = '';
                    if (showLbls) fibLabel += lvl.toFixed(3);
                    if (showPrices) fibLabel += (fibLabel ? '  ' : '') + '(' + priceFib.toFixed(2) + ')';
                    ctx.fillText(fibLabel, viewport.left + 8, yFib - 4);
                }
            }
            ctx.setLineDash([]);
            ctx.lineWidth = lw;

            // Trend line — diagonal dashed line connecting the two anchor points
            var fA1 = _tvToPixel(chartId, d.t1, d.p1);
            var fA2 = _tvToPixel(chartId, d.t2, d.p2);
            if (fA1 && fA2) {
                ctx.strokeStyle = col;
                ctx.lineWidth = lw;
                ctx.setLineDash([6, 4]);
                ctx.globalAlpha = 0.6;
                ctx.beginPath();
                ctx.moveTo(fA1.x, fA1.y);
                ctx.lineTo(fA2.x, fA2.y);
                ctx.stroke();
                ctx.globalAlpha = 1.0;
                ctx.setLineDash([]);
            }
        }
    } else if (d.type === 'fib_extension') {
        // Trend-Based Fib Extension: 3 anchor points (A, B, C)
        // Levels project from C using the A→B distance
        var feA = _tvToPixel(chartId, d.t1, d.p1);
        var feB = _tvToPixel(chartId, d.t2, d.p2);
        var feC = d.t3 !== undefined ? _tvToPixel(chartId, d.t3, d.p3) : null;
        if (feA && feB) {
            // Draw the A→B leg
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.setLineDash([]);
            ctx.beginPath(); ctx.moveTo(feA.x, feA.y); ctx.lineTo(feB.x, feB.y); ctx.stroke();
            if (feC) {
                // Draw B→C leg
                ctx.setLineDash([4, 3]);
                ctx.beginPath(); ctx.moveTo(feB.x, feB.y); ctx.lineTo(feC.x, feC.y); ctx.stroke();
                ctx.setLineDash([]);
                // Extension levels project from C using AB price range
                var abRange = d.p2 - d.p1;
                var extDefLevels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1, 1.618, 2.618, 4.236];
                var fibLevels = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : extDefLevels;
                var fibColors = (d.fibColors && d.fibColors.length) ? d.fibColors : _getFibColors();
                var fibEnabled = d.fibEnabled || [];
                var showLbls = d.showLabels !== false;
                var showPrices = d.showPrices !== false;
                for (var fi = 0; fi < fibLevels.length; fi++) {
                    if (fibEnabled[fi] === false) continue;
                    var lvl = fibLevels[fi];
                    var extPrice = d.p3 + abRange * lvl;
                    var yExt = series.priceToCoordinate(extPrice);
                    if (yExt === null) continue;
                    var fc = fibColors[fi % fibColors.length] || col;
                    // Zone fill between this level and next
                    if (d.fillEnabled !== false && fi < fibLevels.length - 1 && fibEnabled[fi + 1] !== false) {
                        var nextPrice = d.p3 + abRange * fibLevels[fi + 1];
                        var yNext = series.priceToCoordinate(nextPrice);
                        if (yNext !== null) {
                            ctx.fillStyle = fc;
                            ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.06;
                            ctx.fillRect(0, Math.min(yExt, yNext), w, Math.abs(yNext - yExt));
                            ctx.globalAlpha = 1.0;
                        }
                    }
                    ctx.strokeStyle = fc;
                    ctx.lineWidth = lvl === 0 || lvl === 1 ? lw : Math.max(1, lw - 1);
                    ctx.setLineDash(lvl === 0 || lvl === 1 ? [] : [4, 3]);
                    ctx.beginPath(); ctx.moveTo(0, yExt); ctx.lineTo(w, yExt); ctx.stroke();
                    if (showLbls || showPrices) {
                        ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                        ctx.fillStyle = fc;
                        var lbl = '';
                        if (showLbls) lbl += lvl.toFixed(3);
                        if (showPrices) lbl += (lbl ? '  (' : '') + extPrice.toFixed(2) + (lbl ? ')' : '');
                        ctx.fillText(lbl, viewport.left + 8, yExt - 4);
                    }
                }
                ctx.setLineDash([]);
                ctx.lineWidth = lw;
            }
        }
    } else if (d.type === 'fib_channel') {
        // Fib Channel: two trend lines (A→B and parallel through C) with fib levels between
        var fcA = _tvToPixel(chartId, d.t1, d.p1);
        var fcB = _tvToPixel(chartId, d.t2, d.p2);
        var fcC = d.t3 !== undefined ? _tvToPixel(chartId, d.t3, d.p3) : null;
        if (fcA && fcB) {
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.setLineDash([]);
            ctx.beginPath(); ctx.moveTo(fcA.x, fcA.y); ctx.lineTo(fcB.x, fcB.y); ctx.stroke();
            if (fcC) {
                // Perpendicular offset from A→B line to C
                var abDx = fcB.x - fcA.x, abDy = fcB.y - fcA.y;
                var abLen = Math.sqrt(abDx * abDx + abDy * abDy);
                if (abLen > 0) {
                    // Perpendicular offset = distance from C to line AB
                    var cOff = ((fcC.x - fcA.x) * (-abDy / abLen) + (fcC.y - fcA.y) * (abDx / abLen));
                    var px = -abDy / abLen, py = abDx / abLen;
                    var fibLevels = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : _FIB_LEVELS.slice();
                    var fibColors = (d.fibColors && d.fibColors.length) ? d.fibColors : _getFibColors();
                    var fibEnabled = d.fibEnabled || [];
                    var showLbls = d.showLabels !== false;
                    for (var fi = 0; fi < fibLevels.length; fi++) {
                        if (fibEnabled[fi] === false) continue;
                        var lvl = fibLevels[fi];
                        var off = cOff * lvl;
                        var fc = fibColors[fi] || col;
                        ctx.strokeStyle = fc;
                        ctx.lineWidth = lvl === 0 || lvl === 1 ? lw : Math.max(1, lw - 1);
                        ctx.setLineDash(lvl === 0 || lvl === 1 ? [] : [4, 3]);
                        ctx.beginPath();
                        ctx.moveTo(fcA.x + px * off, fcA.y + py * off);
                        ctx.lineTo(fcB.x + px * off, fcB.y + py * off);
                        ctx.stroke();
                        if (showLbls) {
                            ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                            ctx.fillStyle = fc;
                            ctx.fillText(lvl.toFixed(3), fcA.x + px * off + 4, fcA.y + py * off - 4);
                        }
                    }
                    // Fill between 0 and 1 levels
                    if (d.fillEnabled !== false) {
                        ctx.fillStyle = d.fillColor || col;
                        ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.04;
                        ctx.beginPath();
                        ctx.moveTo(fcA.x, fcA.y);
                        ctx.lineTo(fcB.x, fcB.y);
                        ctx.lineTo(fcB.x + px * cOff, fcB.y + py * cOff);
                        ctx.lineTo(fcA.x + px * cOff, fcA.y + py * cOff);
                        ctx.closePath();
                        ctx.fill();
                        ctx.globalAlpha = 1.0;
                    }
                    ctx.setLineDash([]);
                    ctx.lineWidth = lw;
                }
            }
        }
    } else if (d.type === 'fib_timezone') {
        // Fib Time Zone: vertical lines at fibonacci time intervals from anchor
        var ftzA = _tvToPixel(chartId, d.t1, d.p1);
        var ftzB = _tvToPixel(chartId, d.t2, d.p2);
        if (ftzA && ftzB) {
            var tDiff = d.t2 - d.t1;
            var fibNums = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144];
            var fibColors = (d.fibColors && d.fibColors.length) ? d.fibColors : _getFibColors();
            var fibTzEnabled = d.fibEnabled || [];
            var showLbls = d.showLabels !== false;
            for (var fi = 0; fi < fibNums.length; fi++) {
                if (fibTzEnabled[fi] === false) continue;
                var tLine = d.t1 + tDiff * fibNums[fi];
                var xPx = _tvToPixel(chartId, tLine, d.p1);
                if (!xPx) continue;
                if (xPx.x < 0 || xPx.x > w) continue;
                var fc = fibColors[fi % fibColors.length] || col;
                ctx.strokeStyle = fc;
                ctx.lineWidth = fi < 3 ? lw : Math.max(1, lw - 1);
                ctx.setLineDash(fi < 3 ? [] : [4, 3]);
                ctx.beginPath(); ctx.moveTo(xPx.x, 0); ctx.lineTo(xPx.x, h); ctx.stroke();
                if (showLbls) {
                    ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                    ctx.fillStyle = fc;
                    ctx.fillText(String(fibNums[fi]), xPx.x + 3, 14);
                }
            }
            ctx.setLineDash([]);
            ctx.lineWidth = lw;
            // Trend line connecting anchors
            if (d.showTrendLine !== false) {
                ctx.strokeStyle = col;
                ctx.setLineDash([6, 4]);
                ctx.globalAlpha = 0.5;
                ctx.beginPath(); ctx.moveTo(ftzA.x, ftzA.y); ctx.lineTo(ftzB.x, ftzB.y); ctx.stroke();
                ctx.globalAlpha = 1.0;
                ctx.setLineDash([]);
            }
        }
    } else if (d.type === 'fib_fan') {
        // Fib Speed Resistance Fan: fan lines from anchor A through fib-interpolated points on B
        var ffA = _tvToPixel(chartId, d.t1, d.p1);
        var ffB = _tvToPixel(chartId, d.t2, d.p2);
        if (ffA && ffB) {
            var fibLevels = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : _FIB_LEVELS.slice();
            var fibColors = (d.fibColors && d.fibColors.length) ? d.fibColors : _getFibColors();
            var fibEnabled = d.fibEnabled || [];
            var showLbls = d.showLabels !== false;
            var fdx = ffB.x - ffA.x, fdy = ffB.y - ffA.y;
            for (var fi = 0; fi < fibLevels.length; fi++) {
                if (fibEnabled[fi] === false) continue;
                var lvl = fibLevels[fi];
                if (lvl === 0) continue; // 0 level = horizontal through A
                var fc = fibColors[fi] || col;
                // Fan line from A to point at (B.x, lerp(A.y, B.y, lvl))
                var fanY = ffA.y + fdy * lvl;
                ctx.strokeStyle = fc;
                ctx.lineWidth = lvl === 1 ? lw : Math.max(1, lw - 1);
                ctx.setLineDash(lvl === 1 ? [] : [4, 3]);
                // Extend the line beyond B
                var extLen = 4000;
                var fDx = ffB.x - ffA.x, fDy = fanY - ffA.y;
                var fLen = Math.sqrt(fDx * fDx + fDy * fDy);
                if (fLen > 0) {
                    var eX = ffA.x + (fDx / fLen) * extLen;
                    var eY = ffA.y + (fDy / fLen) * extLen;
                    ctx.beginPath(); ctx.moveTo(ffA.x, ffA.y); ctx.lineTo(eX, eY); ctx.stroke();
                }
                if (showLbls) {
                    ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                    ctx.fillStyle = fc;
                    ctx.fillText(lvl.toFixed(3), ffB.x + 4, fanY - 4);
                }
            }
            // Fill between adjacent fan lines
            if (d.fillEnabled !== false) {
                ctx.fillStyle = col;
                ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.03;
                for (var fi = 0; fi < fibLevels.length - 1; fi++) {
                    if (fibEnabled[fi] === false || fibEnabled[fi + 1] === false) continue;
                    var y1 = ffA.y + fdy * fibLevels[fi];
                    var y2 = ffA.y + fdy * fibLevels[fi + 1];
                    ctx.beginPath();
                    ctx.moveTo(ffA.x, ffA.y);
                    ctx.lineTo(ffB.x, y1);
                    ctx.lineTo(ffB.x, y2);
                    ctx.closePath();
                    ctx.fill();
                }
                ctx.globalAlpha = 1.0;
            }
            ctx.setLineDash([]);
            ctx.lineWidth = lw;
        }
    } else if (d.type === 'fib_arc') {
        // Fib Speed Resistance Arcs: semi-circle arcs centered at A, opening away from B
        var faA = _tvToPixel(chartId, d.t1, d.p1);
        var faB = _tvToPixel(chartId, d.t2, d.p2);
        if (faA && faB) {
            var abDist = Math.sqrt(Math.pow(faB.x - faA.x, 2) + Math.pow(faB.y - faA.y, 2));
            var fibLevels = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : _FIB_LEVELS.slice();
            var fibColors = (d.fibColors && d.fibColors.length) ? d.fibColors : _getFibColors();
            var fibEnabled = d.fibEnabled || [];
            var showLbls = d.showLabels !== false;
            // Angle from A to B — arcs open in the opposite direction (away from B)
            var abAngle = Math.atan2(faB.y - faA.y, faB.x - faA.x);
            var arcStart = abAngle + Math.PI / 2;
            var arcEnd = abAngle - Math.PI / 2;
            // Trend line
            if (d.showTrendLine !== false) {
                ctx.strokeStyle = col;
                ctx.setLineDash([6, 4]);
                ctx.globalAlpha = 0.5;
                ctx.beginPath(); ctx.moveTo(faA.x, faA.y); ctx.lineTo(faB.x, faB.y); ctx.stroke();
                ctx.globalAlpha = 1.0;
                ctx.setLineDash([]);
            }
            for (var fi = 0; fi < fibLevels.length; fi++) {
                if (fibEnabled[fi] === false) continue;
                var lvl = fibLevels[fi];
                if (lvl === 0) continue;
                var fc = fibColors[fi] || col;
                var arcR = abDist * lvl;
                ctx.strokeStyle = fc;
                ctx.lineWidth = lvl === 1 ? lw : Math.max(1, lw - 1);
                ctx.setLineDash(lvl === 1 ? [] : [4, 3]);
                ctx.beginPath();
                ctx.arc(faA.x, faA.y, arcR, arcStart, arcEnd);
                ctx.stroke();
                if (showLbls) {
                    ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                    ctx.fillStyle = fc;
                    // Label at the end of the arc (perpendicular to AB)
                    var lblX = faA.x + arcR * Math.cos(arcEnd) + 3;
                    var lblY = faA.y + arcR * Math.sin(arcEnd) - 4;
                    ctx.fillText(lvl.toFixed(3), lblX, lblY);
                }
            }
            ctx.setLineDash([]);
            ctx.lineWidth = lw;
        }
    } else if (d.type === 'fib_circle') {
        // Fib Circles: concentric circles centered at midpoint of AB with fib-scaled radii
        var fcirA = _tvToPixel(chartId, d.t1, d.p1);
        var fcirB = _tvToPixel(chartId, d.t2, d.p2);
        if (fcirA && fcirB) {
            var cMidX = (fcirA.x + fcirB.x) / 2, cMidY = (fcirA.y + fcirB.y) / 2;
            var baseR = Math.sqrt(Math.pow(fcirB.x - fcirA.x, 2) + Math.pow(fcirB.y - fcirA.y, 2)) / 2;
            var fibLevels = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : _FIB_LEVELS.slice();
            var fibColors = (d.fibColors && d.fibColors.length) ? d.fibColors : _getFibColors();
            var fibEnabled = d.fibEnabled || [];
            var showLbls = d.showLabels !== false;
            for (var fi = 0; fi < fibLevels.length; fi++) {
                if (fibEnabled[fi] === false) continue;
                var lvl = fibLevels[fi];
                if (lvl === 0) continue;
                var fc = fibColors[fi] || col;
                var cR = baseR * lvl;
                ctx.strokeStyle = fc;
                ctx.lineWidth = lvl === 1 ? lw : Math.max(1, lw - 1);
                ctx.setLineDash(lvl === 1 ? [] : [4, 3]);
                ctx.beginPath();
                ctx.arc(cMidX, cMidY, cR, 0, Math.PI * 2);
                ctx.stroke();
                if (showLbls) {
                    ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                    ctx.fillStyle = fc;
                    ctx.fillText(lvl.toFixed(3), cMidX + cR + 3, cMidY - 4);
                }
            }
            // Trend line
            if (d.showTrendLine !== false) {
                ctx.strokeStyle = col;
                ctx.setLineDash([6, 4]);
                ctx.globalAlpha = 0.5;
                ctx.beginPath(); ctx.moveTo(fcirA.x, fcirA.y); ctx.lineTo(fcirB.x, fcirB.y); ctx.stroke();
                ctx.globalAlpha = 1.0;
                ctx.setLineDash([]);
            }
            ctx.lineWidth = lw;
        }
    } else if (d.type === 'fib_wedge') {
        // Fib Wedge: two trend lines from A→B and A→C with fib levels between them
        var fwA = _tvToPixel(chartId, d.t1, d.p1);
        var fwB = _tvToPixel(chartId, d.t2, d.p2);
        var fwC = d.t3 !== undefined ? _tvToPixel(chartId, d.t3, d.p3) : null;
        if (fwA && fwB) {
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.setLineDash([]);
            // Draw A→B
            ctx.beginPath(); ctx.moveTo(fwA.x, fwA.y); ctx.lineTo(fwB.x, fwB.y); ctx.stroke();
            if (fwC) {
                // Draw A→C
                ctx.beginPath(); ctx.moveTo(fwA.x, fwA.y); ctx.lineTo(fwC.x, fwC.y); ctx.stroke();
                // Fib lines between A→B and A→C
                var fibLevels = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : _FIB_LEVELS.slice();
                var fibColors = (d.fibColors && d.fibColors.length) ? d.fibColors : _getFibColors();
                var fibEnabled = d.fibEnabled || [];
                var showLbls = d.showLabels !== false;
                for (var fi = 0; fi < fibLevels.length; fi++) {
                    if (fibEnabled[fi] === false) continue;
                    var lvl = fibLevels[fi];
                    if (lvl === 0 || lvl === 1) continue;
                    var fc = fibColors[fi] || col;
                    // Interpolated endpoint between B and C
                    var wEndX = fwB.x + (fwC.x - fwB.x) * lvl;
                    var wEndY = fwB.y + (fwC.y - fwB.y) * lvl;
                    ctx.strokeStyle = fc;
                    ctx.lineWidth = Math.max(1, lw - 1);
                    ctx.setLineDash([4, 3]);
                    ctx.beginPath(); ctx.moveTo(fwA.x, fwA.y); ctx.lineTo(wEndX, wEndY); ctx.stroke();
                    if (showLbls) {
                        ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                        ctx.fillStyle = fc;
                        ctx.fillText(lvl.toFixed(3), wEndX + 4, wEndY - 4);
                    }
                }
                // Fill
                if (d.fillEnabled !== false) {
                    ctx.fillStyle = d.fillColor || col;
                    ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.04;
                    ctx.beginPath();
                    ctx.moveTo(fwA.x, fwA.y);
                    ctx.lineTo(fwB.x, fwB.y);
                    ctx.lineTo(fwC.x, fwC.y);
                    ctx.closePath();
                    ctx.fill();
                    ctx.globalAlpha = 1.0;
                }
                ctx.setLineDash([]);
                ctx.lineWidth = lw;
            }
        }
    } else if (d.type === 'pitchfan') {
        // Pitchfan: median line from A to midpoint(B,C), with fan lines from A through fib divisions
        var pfA = _tvToPixel(chartId, d.t1, d.p1);
        var pfB = _tvToPixel(chartId, d.t2, d.p2);
        var pfC = d.t3 !== undefined ? _tvToPixel(chartId, d.t3, d.p3) : null;
        if (pfA && pfB) {
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.setLineDash([]);
            ctx.beginPath(); ctx.moveTo(pfA.x, pfA.y); ctx.lineTo(pfB.x, pfB.y); ctx.stroke();
            if (pfC) {
                ctx.beginPath(); ctx.moveTo(pfA.x, pfA.y); ctx.lineTo(pfC.x, pfC.y); ctx.stroke();
                // Median line to midpoint of B and C
                var pfMidX = (pfB.x + pfC.x) / 2, pfMidY = (pfB.y + pfC.y) / 2;
                if (d.showMedian !== false) {
                    ctx.strokeStyle = d.medianColor || col;
                    ctx.setLineDash([6, 4]);
                    ctx.beginPath(); ctx.moveTo(pfA.x, pfA.y); ctx.lineTo(pfMidX, pfMidY); ctx.stroke();
                    ctx.setLineDash([]);
                    ctx.strokeStyle = col;
                }
                // Fan lines from A through fib divisions between B and C
                var pfDefLevels = [0.236, 0.382, 0.5, 0.618, 0.786];
                var fibLevels = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : pfDefLevels;
                var fibColors = (d.fibColors && d.fibColors.length) ? d.fibColors : _getFibColors();
                var fibEnabled = d.fibEnabled || [];
                var showLbls = d.showLabels !== false;
                for (var fi = 0; fi < fibLevels.length; fi++) {
                    if (fibEnabled[fi] === false) continue;
                    var lvl = fibLevels[fi];
                    var fc = fibColors[fi] || col;
                    var pfTgtX = pfB.x + (pfC.x - pfB.x) * lvl;
                    var pfTgtY = pfB.y + (pfC.y - pfB.y) * lvl;
                    // Extend from A through target point
                    var pfDx = pfTgtX - pfA.x, pfDy = pfTgtY - pfA.y;
                    var pfLen = Math.sqrt(pfDx * pfDx + pfDy * pfDy);
                    if (pfLen > 0) {
                        var pfExt = 4000;
                        ctx.strokeStyle = fc;
                        ctx.lineWidth = Math.max(1, lw - 1);
                        ctx.setLineDash([4, 3]);
                        ctx.beginPath();
                        ctx.moveTo(pfA.x, pfA.y);
                        ctx.lineTo(pfA.x + (pfDx / pfLen) * pfExt, pfA.y + (pfDy / pfLen) * pfExt);
                        ctx.stroke();
                    }
                    if (showLbls) {
                        ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                        ctx.fillStyle = fc;
                        ctx.fillText(lvl.toFixed(3), pfTgtX + 4, pfTgtY - 4);
                    }
                }
                ctx.setLineDash([]);
                ctx.lineWidth = lw;
            }
        }
    } else if (d.type === 'fib_time') {
        // Trend-Based Fib Time: 3-point, A→B time range projected from C as vertical lines
        var ftA = _tvToPixel(chartId, d.t1, d.p1);
        var ftB = _tvToPixel(chartId, d.t2, d.p2);
        var ftC = d.t3 !== undefined ? _tvToPixel(chartId, d.t3, d.p3) : null;
        if (ftA && ftB) {
            var tDiff = d.t2 - d.t1;
            // Trend line A→B
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.setLineDash([6, 4]);
            ctx.globalAlpha = 0.5;
            ctx.beginPath(); ctx.moveTo(ftA.x, ftA.y); ctx.lineTo(ftB.x, ftB.y); ctx.stroke();
            if (ftC) {
                ctx.beginPath(); ctx.moveTo(ftB.x, ftB.y); ctx.lineTo(ftC.x, ftC.y); ctx.stroke();
            }
            ctx.globalAlpha = 1.0;
            ctx.setLineDash([]);
            // Vertical lines at fib ratios of AB time, projected from C
            var projT = ftC ? d.t3 : d.t1;
            var ftLevels = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : [0, 0.382, 0.5, 0.618, 1, 1.382, 1.618, 2, 2.618, 4.236];
            var fibColors = (d.fibColors && d.fibColors.length) ? d.fibColors : _getFibColors();
            var fibEnabled = d.fibEnabled || [];
            var showLbls = d.showLabels !== false;
            for (var fi = 0; fi < ftLevels.length; fi++) {
                if (fibEnabled[fi] === false) continue;
                var tLine = projT + tDiff * ftLevels[fi];
                var xPx = _tvToPixel(chartId, tLine, d.p1);
                if (!xPx) continue;
                if (xPx.x < 0 || xPx.x > w) continue;
                var fc = fibColors[fi % fibColors.length] || col;
                ctx.strokeStyle = fc;
                ctx.lineWidth = (ftLevels[fi] === 0 || ftLevels[fi] === 1) ? lw : Math.max(1, lw - 1);
                ctx.setLineDash((ftLevels[fi] === 0 || ftLevels[fi] === 1) ? [] : [4, 3]);
                ctx.beginPath(); ctx.moveTo(xPx.x, 0); ctx.lineTo(xPx.x, h); ctx.stroke();
                if (showLbls) {
                    ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                    ctx.fillStyle = fc;
                    ctx.fillText(ftLevels[fi].toFixed(3), xPx.x + 3, 14);
                }
            }
            ctx.setLineDash([]);
            ctx.lineWidth = lw;
        }
    } else if (d.type === 'fib_spiral') {
        // Fib Spiral: golden logarithmic spiral from center A through B
        var fsA = _tvToPixel(chartId, d.t1, d.p1);
        var fsB = _tvToPixel(chartId, d.t2, d.p2);
        if (fsA && fsB) {
            var fsDx = fsB.x - fsA.x, fsDy = fsB.y - fsA.y;
            var fsR = Math.sqrt(fsDx * fsDx + fsDy * fsDy);
            var fsStartAngle = Math.atan2(fsDy, fsDx);
            var fsPhi = 1.6180339887;
            var fsGrowth = Math.log(fsPhi) / (Math.PI / 2);
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.beginPath();
            var fsNPts = 400;
            var fsMinTheta = -4 * Math.PI;
            var fsMaxTheta = 4 * Math.PI;
            var fsFirst = true;
            for (var fi = 0; fi <= fsNPts; fi++) {
                var theta = fsMinTheta + (fi / fsNPts) * (fsMaxTheta - fsMinTheta);
                var r = fsR * Math.exp(fsGrowth * theta);
                if (r < 1 || r > 5000) { fsFirst = true; continue; }
                var sx = fsA.x + r * Math.cos(fsStartAngle + theta);
                var sy = fsA.y + r * Math.sin(fsStartAngle + theta);
                if (fsFirst) { ctx.moveTo(sx, sy); fsFirst = false; }
                else ctx.lineTo(sx, sy);
            }
            ctx.stroke();
            // AB reference line
            ctx.setLineDash([6, 4]);
            ctx.globalAlpha = 0.5;
            ctx.beginPath(); ctx.moveTo(fsA.x, fsA.y); ctx.lineTo(fsB.x, fsB.y); ctx.stroke();
            ctx.globalAlpha = 1.0;
            ctx.setLineDash([]);
        }
    } else if (d.type === 'gann_box') {
        // Gann Box: rectangular grid with diagonal, price/time subdivisions
        var gbA = _tvToPixel(chartId, d.t1, d.p1);
        var gbB = _tvToPixel(chartId, d.t2, d.p2);
        if (gbA && gbB) {
            var gblx = Math.min(gbA.x, gbB.x), gbrx = Math.max(gbA.x, gbB.x);
            var gbty = Math.min(gbA.y, gbB.y), gbby = Math.max(gbA.y, gbB.y);
            var gbW = gbrx - gblx, gbH = gbby - gbty;
            // Box outline
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.strokeRect(gblx, gbty, gbW, gbH);
            // Horizontal grid lines
            var gbLevels = d.gannLevels || [0.25, 0.5, 0.75];
            var gbColors = (d.fibColors && d.fibColors.length) ? d.fibColors : [];
            var gbEnabled = d.fibEnabled || [];
            for (var gi = 0; gi < gbLevels.length; gi++) {
                if (gbEnabled[gi] === false) continue;
                var gy = gbty + gbH * gbLevels[gi];
                ctx.strokeStyle = gbColors[gi] || col;
                ctx.lineWidth = Math.max(1, lw - 1);
                ctx.setLineDash([4, 3]);
                ctx.beginPath(); ctx.moveTo(gblx, gy); ctx.lineTo(gbrx, gy); ctx.stroke();
            }
            // Vertical grid lines
            for (var gi = 0; gi < gbLevels.length; gi++) {
                if (gbEnabled[gi] === false) continue;
                var gx = gblx + gbW * gbLevels[gi];
                ctx.strokeStyle = gbColors[gi] || col;
                ctx.lineWidth = Math.max(1, lw - 1);
                ctx.setLineDash([4, 3]);
                ctx.beginPath(); ctx.moveTo(gx, gbty); ctx.lineTo(gx, gbby); ctx.stroke();
            }
            ctx.setLineDash([]);
            // Main diagonal
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.beginPath(); ctx.moveTo(gblx, gbby); ctx.lineTo(gbrx, gbty); ctx.stroke();
            // Counter-diagonal
            ctx.setLineDash([4, 3]);
            ctx.beginPath(); ctx.moveTo(gblx, gbty); ctx.lineTo(gbrx, gbby); ctx.stroke();
            ctx.setLineDash([]);
            // Background fill
            if (d.fillEnabled !== false) {
                ctx.fillStyle = d.fillColor || col;
                ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.03;
                ctx.fillRect(gblx, gbty, gbW, gbH);
                ctx.globalAlpha = 1.0;
            }
        }
    } else if (d.type === 'gann_square_fixed') {
        // Gann Square Fixed: fixed-ratio square grid
        var gsfA = _tvToPixel(chartId, d.t1, d.p1);
        var gsfB = _tvToPixel(chartId, d.t2, d.p2);
        if (gsfA && gsfB) {
            var gsfDx = Math.abs(gsfB.x - gsfA.x), gsfDy = Math.abs(gsfB.y - gsfA.y);
            var gsfSize = Math.max(gsfDx, gsfDy);
            var gsfX = Math.min(gsfA.x, gsfB.x), gsfY = Math.min(gsfA.y, gsfB.y);
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.strokeRect(gsfX, gsfY, gsfSize, gsfSize);
            var gsfLevels = d.gannLevels || [0.25, 0.5, 0.75];
            var gsfColors = (d.fibColors && d.fibColors.length) ? d.fibColors : [];
            var gsfEnabled = d.fibEnabled || [];
            for (var gi = 0; gi < gsfLevels.length; gi++) {
                if (gsfEnabled[gi] === false) continue;
                var gy = gsfY + gsfSize * gsfLevels[gi];
                var gx = gsfX + gsfSize * gsfLevels[gi];
                ctx.strokeStyle = gsfColors[gi] || col;
                ctx.lineWidth = Math.max(1, lw - 1);
                ctx.setLineDash([4, 3]);
                ctx.beginPath(); ctx.moveTo(gsfX, gy); ctx.lineTo(gsfX + gsfSize, gy); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(gx, gsfY); ctx.lineTo(gx, gsfY + gsfSize); ctx.stroke();
            }
            ctx.setLineDash([]);
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.beginPath(); ctx.moveTo(gsfX, gsfY + gsfSize); ctx.lineTo(gsfX + gsfSize, gsfY); ctx.stroke();
            ctx.setLineDash([4, 3]);
            ctx.beginPath(); ctx.moveTo(gsfX, gsfY); ctx.lineTo(gsfX + gsfSize, gsfY + gsfSize); ctx.stroke();
            ctx.setLineDash([]);
            if (d.fillEnabled !== false) {
                ctx.fillStyle = d.fillColor || col;
                ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.03;
                ctx.fillRect(gsfX, gsfY, gsfSize, gsfSize);
                ctx.globalAlpha = 1.0;
            }
        }
    } else if (d.type === 'gann_square') {
        // Gann Square: rectangular grid with diagonals and mid-cross
        var gsA = _tvToPixel(chartId, d.t1, d.p1);
        var gsB = _tvToPixel(chartId, d.t2, d.p2);
        if (gsA && gsB) {
            var gslx = Math.min(gsA.x, gsB.x), gsrx = Math.max(gsA.x, gsB.x);
            var gsty = Math.min(gsA.y, gsB.y), gsby = Math.max(gsA.y, gsB.y);
            var gsW = gsrx - gslx, gsH = gsby - gsty;
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.strokeRect(gslx, gsty, gsW, gsH);
            var gsLevels = d.gannLevels || [0.25, 0.5, 0.75];
            var gsColors = (d.fibColors && d.fibColors.length) ? d.fibColors : [];
            var gsEnabled = d.fibEnabled || [];
            for (var gi = 0; gi < gsLevels.length; gi++) {
                if (gsEnabled[gi] === false) continue;
                var gy = gsty + gsH * gsLevels[gi];
                var gx = gslx + gsW * gsLevels[gi];
                ctx.strokeStyle = gsColors[gi] || col;
                ctx.lineWidth = Math.max(1, lw - 1);
                ctx.setLineDash([4, 3]);
                ctx.beginPath(); ctx.moveTo(gslx, gy); ctx.lineTo(gsrx, gy); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(gx, gsty); ctx.lineTo(gx, gsby); ctx.stroke();
            }
            ctx.setLineDash([]);
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.beginPath(); ctx.moveTo(gslx, gsby); ctx.lineTo(gsrx, gsty); ctx.stroke();
            ctx.setLineDash([4, 3]);
            ctx.beginPath(); ctx.moveTo(gslx, gsty); ctx.lineTo(gsrx, gsby); ctx.stroke();
            ctx.setLineDash([]);
            // Mid-cross
            var gsMidX = (gslx + gsrx) / 2, gsMidY = (gsty + gsby) / 2;
            ctx.setLineDash([2, 2]);
            ctx.globalAlpha = 0.4;
            ctx.beginPath(); ctx.moveTo(gsMidX, gsty); ctx.lineTo(gsMidX, gsby); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(gslx, gsMidY); ctx.lineTo(gsrx, gsMidY); ctx.stroke();
            ctx.globalAlpha = 1.0;
            ctx.setLineDash([]);
            if (d.fillEnabled !== false) {
                ctx.fillStyle = d.fillColor || col;
                ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.03;
                ctx.fillRect(gslx, gsty, gsW, gsH);
                ctx.globalAlpha = 1.0;
            }
        }
    } else if (d.type === 'gann_fan') {
        // Gann Fan: fan lines from A at standard Gann angles, B defines the 1x1 line
        var gfA = _tvToPixel(chartId, d.t1, d.p1);
        var gfB = _tvToPixel(chartId, d.t2, d.p2);
        if (gfA && gfB) {
            var gfDx = gfB.x - gfA.x, gfDy = gfB.y - gfA.y;
            var gannAngles = [
                { name: '1\u00d78', ratio: 0.125 },
                { name: '1\u00d74', ratio: 0.25 },
                { name: '1\u00d73', ratio: 0.333 },
                { name: '1\u00d72', ratio: 0.5 },
                { name: '1\u00d71', ratio: 1 },
                { name: '2\u00d71', ratio: 2 },
                { name: '3\u00d71', ratio: 3 },
                { name: '4\u00d71', ratio: 4 },
                { name: '8\u00d71', ratio: 8 }
            ];
            var gfColors = (d.fibColors && d.fibColors.length) ? d.fibColors : [];
            var gfEnabled = d.fibEnabled || [];
            var showLbls = d.showLabels !== false;
            for (var gi = 0; gi < gannAngles.length; gi++) {
                if (gfEnabled[gi] === false) continue;
                var gRatio = gannAngles[gi].ratio;
                var fanEndX = gfA.x + gfDx;
                var fanEndY = gfA.y + gfDy * gRatio;
                var fDx = fanEndX - gfA.x, fDy = fanEndY - gfA.y;
                var fLen = Math.sqrt(fDx * fDx + fDy * fDy);
                if (fLen > 0) {
                    var extLen = 4000;
                    var eX = gfA.x + (fDx / fLen) * extLen;
                    var eY = gfA.y + (fDy / fLen) * extLen;
                    ctx.strokeStyle = gfColors[gi] || col;
                    ctx.lineWidth = gRatio === 1 ? lw : Math.max(1, lw - 1);
                    ctx.setLineDash(gRatio === 1 ? [] : [4, 3]);
                    ctx.beginPath(); ctx.moveTo(gfA.x, gfA.y); ctx.lineTo(eX, eY); ctx.stroke();
                    if (showLbls) {
                        ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                        ctx.fillStyle = gfColors[gi] || col;
                        ctx.fillText(gannAngles[gi].name, fanEndX + 4, fanEndY - 4);
                    }
                }
            }
            ctx.setLineDash([]);
            ctx.lineWidth = lw;
        }
    } else if (d.type === 'measure') {
        var m1 = _tvToPixel(chartId, d.t1, d.p1);
        var m2 = _tvToPixel(chartId, d.t2, d.p2);
        if (m1 && m2) {
            var priceDiff = d.p2 - d.p1;
            var pctChange = d.p1 !== 0 ? ((priceDiff / d.p1) * 100) : 0;
            var isUp = priceDiff >= 0;
            var measureUpCol = d.colorUp || _cssVar('--pywry-draw-measure-up');
            var measureDnCol = d.colorDown || _cssVar('--pywry-draw-measure-down');
            var measureCol = isUp ? measureUpCol : measureDnCol;
            ctx.strokeStyle = measureCol;
            ctx.fillStyle = measureCol;

            // Shaded rectangle between the two points (like TV)
            var mrx = Math.min(m1.x, m2.x), mry = Math.min(m1.y, m2.y);
            var mrw = Math.abs(m2.x - m1.x), mrh = Math.abs(m2.y - m1.y);
            ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.08;
            ctx.fillRect(mrx, mry, mrw, mrh);
            ctx.globalAlpha = 1.0;

            // Vertical dashed lines at each x
            ctx.setLineDash([3, 3]);
            ctx.beginPath();
            ctx.moveTo(m1.x, Math.min(m1.y, m2.y) - 20);
            ctx.lineTo(m1.x, Math.max(m1.y, m2.y) + 20);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(m2.x, Math.min(m1.y, m2.y) - 20);
            ctx.lineTo(m2.x, Math.max(m1.y, m2.y) + 20);
            ctx.stroke();
            ctx.setLineDash([]);

            // Horizontal lines at each price
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(mrx, m1.y);
            ctx.lineTo(mrx + mrw, m1.y);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(mrx, m2.y);
            ctx.lineTo(mrx + mrw, m2.y);
            ctx.stroke();
            ctx.lineWidth = lw;

            // Info label (like TV: "−15.76 (−5.64%) −1,576")
            var label = (isUp ? '+' : '') + priceDiff.toFixed(2) +
                        ' (' + (isUp ? '+' : '') + pctChange.toFixed(2) + '%)';
            var mFontSize = d.fontSize || 12;
            ctx.font = 'bold ' + mFontSize + 'px -apple-system,BlinkMacSystemFont,sans-serif';
            var met = ctx.measureText(label);
            var boxPad = 6;
            var bx = (m1.x + m2.x) / 2 - met.width / 2 - boxPad;
            var by = Math.min(m1.y, m2.y) - 28;
            // Background pill
            ctx.fillStyle = measureCol;
            ctx.globalAlpha = 0.9;
            _roundRect(ctx, bx, by, met.width + boxPad * 2, 22, 4);
            ctx.fill();
            ctx.globalAlpha = 1.0;
            ctx.fillStyle = _cssVar('--pywry-draw-label-text');
            ctx.textBaseline = 'middle';
            ctx.fillText(label, bx + boxPad, by + 11);
            ctx.textBaseline = 'alphabetic';
        }
    } else if (d.type === 'ray') {
        // Ray: from point A through point B, extending to infinity in B direction
        var ra = _tvToPixel(chartId, d.t1, d.p1);
        var rb = _tvToPixel(chartId, d.t2, d.p2);
        if (ra && rb) {
            var rdx = rb.x - ra.x, rdy = rb.y - ra.y;
            var rlen = Math.sqrt(rdx * rdx + rdy * rdy);
            if (rlen > 0) {
                var ext = 4000;
                var rux = rdx / rlen, ruy = rdy / rlen;
                ctx.beginPath();
                ctx.moveTo(ra.x, ra.y);
                ctx.lineTo(ra.x + rux * ext, ra.y + ruy * ext);
                ctx.stroke();
            }
            // Text annotation
            if (d.text) {
                var rMidX = (ra.x + rb.x) / 2, rMidY = (ra.y + rb.y) / 2;
                var rFs = d.textFontSize || 12;
                var rTStyle = (d.textItalic ? 'italic ' : '') + (d.textBold ? 'bold ' : '');
                ctx.font = rTStyle + rFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
                ctx.fillStyle = d.textColor || col;
                ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
                ctx.fillText(d.text, rMidX, rMidY - 6);
                ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
            }
        }
    } else if (d.type === 'extended_line') {
        // Extended line: infinite in both directions through A and B
        var ea = _tvToPixel(chartId, d.t1, d.p1);
        var eb = _tvToPixel(chartId, d.t2, d.p2);
        if (ea && eb) {
            var edx = eb.x - ea.x, edy = eb.y - ea.y;
            var elen = Math.sqrt(edx * edx + edy * edy);
            if (elen > 0) {
                var eext = 4000;
                var eux = edx / elen, euy = edy / elen;
                ctx.beginPath();
                ctx.moveTo(ea.x - eux * eext, ea.y - euy * eext);
                ctx.lineTo(eb.x + eux * eext, eb.y + euy * eext);
                ctx.stroke();
            }
            // Text annotation
            if (d.text) {
                var eMidX = (ea.x + eb.x) / 2, eMidY = (ea.y + eb.y) / 2;
                var eFs = d.textFontSize || 12;
                var eTStyle = (d.textItalic ? 'italic ' : '') + (d.textBold ? 'bold ' : '');
                ctx.font = eTStyle + eFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
                ctx.fillStyle = d.textColor || col;
                ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
                ctx.fillText(d.text, eMidX, eMidY - 6);
                ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
            }
        }
    } else if (d.type === 'hray') {
        // Horizontal ray: from anchor point extending right
        var hry = series.priceToCoordinate(d.p1);
        var hra = _tvToPixel(chartId, d.t1, d.p1);
        if (hry !== null && hra) {
            ctx.beginPath();
            ctx.moveTo(hra.x, hry);
            ctx.lineTo(w, hry);
            ctx.stroke();
        }
    } else if (d.type === 'vline') {
        // Vertical line: at a specific time, top to bottom
        var va = _tvToPixel(chartId, d.t1, d.p1 || 0);
        if (va) {
            ctx.beginPath();
            ctx.moveTo(va.x, 0);
            ctx.lineTo(va.x, h);
            ctx.stroke();
        }
    } else if (d.type === 'crossline') {
        // Cross line: vertical + horizontal at a specific point
        var cla = _tvToPixel(chartId, d.t1, d.p1);
        var cly = series.priceToCoordinate(d.p1);
        if (cla && cly !== null) {
            ctx.beginPath();
            ctx.moveTo(cla.x, 0);
            ctx.lineTo(cla.x, h);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(0, cly);
            ctx.lineTo(w, cly);
            ctx.stroke();
        }
    } else if (d.type === 'flat_channel') {
        // Flat top/bottom: two horizontal parallel lines at p1 and p2
        var fy1 = series.priceToCoordinate(d.p1);
        var fy2 = series.priceToCoordinate(d.p2);
        if (fy1 !== null && fy2 !== null) {
            if (d.fillEnabled !== false) {
                ctx.fillStyle = d.fillColor || col;
                ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.08;
                ctx.fillRect(0, Math.min(fy1, fy2), w, Math.abs(fy2 - fy1));
                ctx.globalAlpha = 1.0;
            }
            ctx.beginPath();
            ctx.moveTo(0, fy1);
            ctx.lineTo(w, fy1);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(0, fy2);
            ctx.lineTo(w, fy2);
            ctx.stroke();
        }
    } else if (d.type === 'regression_channel') {
        // Regression channel: linear regression with separate base/up/down lines
        var ra1 = _tvToPixel(chartId, d.t1, d.p1);
        var ra2 = _tvToPixel(chartId, d.t2, d.p2);
        if (ra1 && ra2) {
            var rcUpOff = d.upperDeviation !== undefined ? d.upperDeviation : (d.offset || 30);
            var rcDnOff = d.lowerDeviation !== undefined ? d.lowerDeviation : (d.offset || 30);
            var useUpper = d.useUpperDeviation !== false;
            var useLower = d.useLowerDeviation !== false;
            var ext = 4000;
            // Extend lines support
            var doExtend = !!d.extendLines;
            var dx = ra2.x - ra1.x, dy = ra2.y - ra1.y;
            var len = Math.sqrt(dx * dx + dy * dy);
            var ux = len > 0 ? dx / len : 1, uy = len > 0 ? dy / len : 0;
            var sx1 = ra1.x, sy1 = ra1.y, sx2 = ra2.x, sy2 = ra2.y;
            if (doExtend && len > 0) {
                sx1 = ra1.x - ux * ext; sy1 = ra1.y - uy * ext;
                sx2 = ra2.x + ux * ext; sy2 = ra2.y + uy * ext;
            }
            // Perpendicular unit vector (pointing upward in screen coords)
            var px = len > 0 ? -dy / len : 0, py = len > 0 ? dx / len : -1;
            // Helper: apply per-line style
            function _rcSetLineStyle(lineStyle) {
                ctx.setLineDash(lineStyle === 1 ? [6,4] : lineStyle === 2 ? [2,3] : []);
            }
            // Base line
            if (d.showBaseLine !== false) {
                ctx.strokeStyle = d.baseColor || col;
                ctx.lineWidth = d.baseWidth || defW;
                _rcSetLineStyle(d.baseLineStyle !== undefined ? d.baseLineStyle : (d.lineStyle || 0));
                ctx.beginPath();
                ctx.moveTo(sx1, sy1);
                ctx.lineTo(sx2, sy2);
                ctx.stroke();
            }
            // Upper bound
            if (useUpper && d.showUpLine !== false) {
                ctx.strokeStyle = d.upColor || col;
                ctx.lineWidth = d.upWidth || defW;
                _rcSetLineStyle(d.upLineStyle !== undefined ? d.upLineStyle : 1);
                ctx.globalAlpha = 0.8;
                ctx.beginPath();
                ctx.moveTo(sx1 + px * rcUpOff, sy1 + py * rcUpOff);
                ctx.lineTo(sx2 + px * rcUpOff, sy2 + py * rcUpOff);
                ctx.stroke();
                ctx.globalAlpha = 1.0;
            }
            // Lower bound
            if (useLower && d.showDownLine !== false) {
                ctx.strokeStyle = d.downColor || col;
                ctx.lineWidth = d.downWidth || defW;
                _rcSetLineStyle(d.downLineStyle !== undefined ? d.downLineStyle : 1);
                ctx.globalAlpha = 0.8;
                ctx.beginPath();
                ctx.moveTo(sx1 - px * rcDnOff, sy1 - py * rcDnOff);
                ctx.lineTo(sx2 - px * rcDnOff, sy2 - py * rcDnOff);
                ctx.stroke();
                ctx.globalAlpha = 1.0;
            }
            // Reset stroke for selection handles
            ctx.strokeStyle = col;
            ctx.lineWidth = defW;
            _rcSetLineStyle(d.lineStyle || 0);
            // Fill between upper and lower bounds
            if (d.fillEnabled !== false && (useUpper || useLower)) {
                ctx.fillStyle = d.fillColor || col;
                ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.05;
                var uOff = useUpper ? rcUpOff : 0;
                var dOff = useLower ? rcDnOff : 0;
                ctx.beginPath();
                ctx.moveTo(sx1 + px * uOff, sy1 + py * uOff);
                ctx.lineTo(sx2 + px * uOff, sy2 + py * uOff);
                ctx.lineTo(sx2 - px * dOff, sy2 - py * dOff);
                ctx.lineTo(sx1 - px * dOff, sy1 - py * dOff);
                ctx.closePath();
                ctx.fill();
                ctx.globalAlpha = 1.0;
            }
            // Pearson's R label
            if (d.showPearsonsR) {
                var midX = (ra1.x + ra2.x) / 2, midY = (ra1.y + ra2.y) / 2;
                var vals = _tvGetSeriesDataBetween(chartId, d.t1, d.t2);
                var rVal = vals ? _tvPearsonsR(vals) : null;
                if (rVal !== null) {
                    ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                    ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
                    ctx.fillStyle = col;
                    ctx.globalAlpha = 0.9;
                    ctx.fillText('R = ' + rVal.toFixed(4), midX, midY - 8);
                    ctx.globalAlpha = 1.0;
                }
            }
        }
    } else if (d.type === 'brush' || d.type === 'highlighter') {
        // Brush/Highlighter: freeform path through collected points
        var pts = d.points;
        if (pts && pts.length > 1) {
            if (d.opacity !== undefined && d.opacity < 1) ctx.globalAlpha = d.opacity;
            if (d.type === 'highlighter') {
                ctx.lineCap = 'round';
                ctx.lineJoin = 'round';
            }
            ctx.beginPath();
            var bp0 = _tvToPixel(chartId, pts[0].t, pts[0].p);
            if (bp0) {
                ctx.moveTo(bp0.x, bp0.y);
                for (var bi = 1; bi < pts.length; bi++) {
                    var bpi = _tvToPixel(chartId, pts[bi].t, pts[bi].p);
                    if (bpi) ctx.lineTo(bpi.x, bpi.y);
                }
                ctx.stroke();
            }
            ctx.globalAlpha = 1.0;
        }
    } else if (d.type === 'arrow_marker') {
        // Arrow Marker: fat filled arrow shape from p1 (tail) to p2 (tip)
        if (p1 && p2) {
            var amFillCol = d.fillColor || d.color || defColor;
            var amBorderCol = d.borderColor || d.color || defColor;
            var amTextCol = d.textColor || d.color || defColor;
            var amdx = p2.x - p1.x, amdy = p2.y - p1.y;
            var amLen = Math.sqrt(amdx * amdx + amdy * amdy);
            if (amLen > 1) {
                var amux = amdx / amLen, amuy = amdy / amLen;
                var amnx = -amuy, amny = amux;
                var amHeadLen = Math.min(amLen * 0.38, 80);
                var amHeadW = Math.max(amLen * 0.22, 16);
                var amShaftW = amHeadW * 0.38;
                var ambx = p2.x - amux * amHeadLen, amby = p2.y - amuy * amHeadLen;
                ctx.beginPath();
                ctx.moveTo(p2.x, p2.y);
                ctx.lineTo(ambx + amnx * amHeadW, amby + amny * amHeadW);
                ctx.lineTo(ambx + amnx * amShaftW, amby + amny * amShaftW);
                ctx.lineTo(p1.x + amnx * amShaftW, p1.y + amny * amShaftW);
                ctx.lineTo(p1.x - amnx * amShaftW, p1.y - amny * amShaftW);
                ctx.lineTo(ambx - amnx * amShaftW, amby - amny * amShaftW);
                ctx.lineTo(ambx - amnx * amHeadW, amby - amny * amHeadW);
                ctx.closePath();
                ctx.fillStyle = amFillCol;
                ctx.fill();
                ctx.strokeStyle = amBorderCol;
                ctx.lineWidth = 1;
                ctx.stroke();
            }
            if (d.text) {
                var _amfs = d.fontSize || 16;
                var _amfw = (d.bold ? 'bold ' : '') + (d.italic ? 'italic ' : '');
                ctx.font = _amfw + _amfs + 'px Arial, sans-serif';
                ctx.fillStyle = amTextCol;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                ctx.fillText(d.text, p1.x, p1.y + 8);
            }
        }
    } else if (d.type === 'arrow') {
        // Arrow: thin line with arrowhead at p2
        if (p1 && p2) {
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
            var adx = p2.x - p1.x, ady = p2.y - p1.y;
            var aAngle = Math.atan2(ady, adx);
            var aLen = 12;
            ctx.beginPath();
            ctx.moveTo(p2.x, p2.y);
            ctx.lineTo(p2.x - aLen * Math.cos(aAngle - 0.4), p2.y - aLen * Math.sin(aAngle - 0.4));
            ctx.moveTo(p2.x, p2.y);
            ctx.lineTo(p2.x - aLen * Math.cos(aAngle + 0.4), p2.y - aLen * Math.sin(aAngle + 0.4));
            ctx.stroke();
            if (d.text) {
                var _afs = d.fontSize || 16;
                var _afw = (d.bold ? 'bold ' : '') + (d.italic ? 'italic ' : '');
                ctx.font = _afw + _afs + 'px Arial, sans-serif';
                ctx.fillStyle = col;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                ctx.fillText(d.text, p2.x, p2.y + 6);
            }
        }
    } else if (d.type === 'arrow_mark_up') {
        if (p1) {
            var amu_fc = d.fillColor || d.color || defColor;
            var amu_bc = d.borderColor || d.color || defColor;
            var amu_tc = d.textColor || d.color || defColor;
            var amSz = (d.size || 30) / 2;
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y - amSz);
            ctx.lineTo(p1.x - amSz * 0.7, p1.y + amSz * 0.5);
            ctx.lineTo(p1.x + amSz * 0.7, p1.y + amSz * 0.5);
            ctx.closePath();
            ctx.fillStyle = amu_fc;
            ctx.fill();
            ctx.strokeStyle = amu_bc;
            ctx.lineWidth = 1;
            ctx.stroke();
            if (d.text && mouseOver) {
                var _afs = d.fontSize || 16;
                var _afw = (d.bold ? 'bold ' : '') + (d.italic ? 'italic ' : '');
                ctx.font = _afw + _afs + 'px Arial, sans-serif';
                ctx.fillStyle = amu_tc;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                ctx.fillText(d.text, p1.x, p1.y + amSz * 0.5 + 4);
            }
        }
    } else if (d.type === 'arrow_mark_down') {
        if (p1) {
            var amd_fc = d.fillColor || d.color || defColor;
            var amd_bc = d.borderColor || d.color || defColor;
            var amd_tc = d.textColor || d.color || defColor;
            var amSz = (d.size || 30) / 2;
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y + amSz);
            ctx.lineTo(p1.x - amSz * 0.7, p1.y - amSz * 0.5);
            ctx.lineTo(p1.x + amSz * 0.7, p1.y - amSz * 0.5);
            ctx.closePath();
            ctx.fillStyle = amd_fc;
            ctx.fill();
            ctx.strokeStyle = amd_bc;
            ctx.lineWidth = 1;
            ctx.stroke();
            if (d.text && mouseOver) {
                var _afs = d.fontSize || 16;
                var _afw = (d.bold ? 'bold ' : '') + (d.italic ? 'italic ' : '');
                ctx.font = _afw + _afs + 'px Arial, sans-serif';
                ctx.fillStyle = amd_tc;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'bottom';
                ctx.fillText(d.text, p1.x, p1.y - amSz * 0.5 - 4);
            }
        }
    } else if (d.type === 'arrow_mark_left') {
        if (p1) {
            var aml_fc = d.fillColor || d.color || defColor;
            var aml_bc = d.borderColor || d.color || defColor;
            var aml_tc = d.textColor || d.color || defColor;
            var amSz = (d.size || 30) / 2;
            ctx.beginPath();
            ctx.moveTo(p1.x - amSz, p1.y);
            ctx.lineTo(p1.x + amSz * 0.5, p1.y - amSz * 0.7);
            ctx.lineTo(p1.x + amSz * 0.5, p1.y + amSz * 0.7);
            ctx.closePath();
            ctx.fillStyle = aml_fc;
            ctx.fill();
            ctx.strokeStyle = aml_bc;
            ctx.lineWidth = 1;
            ctx.stroke();
            if (d.text && mouseOver) {
                var _afs = d.fontSize || 16;
                var _afw = (d.bold ? 'bold ' : '') + (d.italic ? 'italic ' : '');
                ctx.font = _afw + _afs + 'px Arial, sans-serif';
                ctx.fillStyle = aml_tc;
                ctx.textAlign = 'left';
                ctx.textBaseline = 'middle';
                ctx.fillText(d.text, p1.x + amSz * 0.5 + 4, p1.y);
            }
        }
    } else if (d.type === 'arrow_mark_right') {
        if (p1) {
            var amr_fc = d.fillColor || d.color || defColor;
            var amr_bc = d.borderColor || d.color || defColor;
            var amr_tc = d.textColor || d.color || defColor;
            var amSz = (d.size || 30) / 2;
            ctx.beginPath();
            ctx.moveTo(p1.x + amSz, p1.y);
            ctx.lineTo(p1.x - amSz * 0.5, p1.y - amSz * 0.7);
            ctx.lineTo(p1.x - amSz * 0.5, p1.y + amSz * 0.7);
            ctx.closePath();
            ctx.fillStyle = amr_fc;
            ctx.fill();
            ctx.strokeStyle = amr_bc;
            ctx.lineWidth = 1;
            ctx.stroke();
            if (d.text && mouseOver) {
                var _afs = d.fontSize || 16;
                var _afw = (d.bold ? 'bold ' : '') + (d.italic ? 'italic ' : '');
                ctx.font = _afw + _afs + 'px Arial, sans-serif';
                ctx.fillStyle = amr_tc;
                ctx.textAlign = 'right';
                ctx.textBaseline = 'middle';
                ctx.fillText(d.text, p1.x - amSz * 0.5 - 4, p1.y);
            }
        }
    } else if (d.type === 'circle') {
        // Circle: center at midpoint, radius = distance/2
        if (p1 && p2) {
            var cx = (p1.x + p2.x) / 2, cy = (p1.y + p2.y) / 2;
            var cr = Math.sqrt(Math.pow(p2.x - p1.x, 2) + Math.pow(p2.y - p1.y, 2)) / 2;
            ctx.beginPath();
            ctx.arc(cx, cy, cr, 0, Math.PI * 2);
            if (d.fillColor) { ctx.fillStyle = d.fillColor; ctx.fill(); }
            ctx.stroke();
        }
    } else if (d.type === 'ellipse') {
        // Ellipse: bounding box from p1 to p2
        if (p1 && p2) {
            var ecx = (p1.x + p2.x) / 2, ecy = (p1.y + p2.y) / 2;
            var erx = Math.abs(p2.x - p1.x) / 2, ery = Math.abs(p2.y - p1.y) / 2;
            ctx.beginPath();
            ctx.ellipse(ecx, ecy, Math.max(erx, 1), Math.max(ery, 1), 0, 0, Math.PI * 2);
            if (d.fillColor) { ctx.fillStyle = d.fillColor; ctx.fill(); }
            ctx.stroke();
        }
    } else if (d.type === 'triangle') {
        // Triangle: 3-point
        if (p1 && p2) {
            var tp3 = d.t3 !== undefined ? _tvToPixel(chartId, d.t3, d.p3) : null;
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            if (tp3) { ctx.lineTo(tp3.x, tp3.y); }
            ctx.closePath();
            if (d.fillColor) { ctx.fillStyle = d.fillColor; ctx.fill(); }
            ctx.stroke();
        }
    } else if (d.type === 'rotated_rect') {
        // Rotated Rectangle: A→B defines one edge, C defines perpendicular width
        if (p1 && p2) {
            var rp3 = d.t3 !== undefined ? _tvToPixel(chartId, d.t3, d.p3) : null;
            if (rp3) {
                // Direction A→B
                var rdx = p2.x - p1.x, rdy = p2.y - p1.y;
                var rlen = Math.sqrt(rdx * rdx + rdy * rdy);
                if (rlen > 0) {
                    var rnx = -rdy / rlen, rny = rdx / rlen;
                    // Project C onto perpendicular to get width
                    var rprojW = (rp3.x - p1.x) * rnx + (rp3.y - p1.y) * rny;
                    ctx.beginPath();
                    ctx.moveTo(p1.x, p1.y);
                    ctx.lineTo(p2.x, p2.y);
                    ctx.lineTo(p2.x + rnx * rprojW, p2.y + rny * rprojW);
                    ctx.lineTo(p1.x + rnx * rprojW, p1.y + rny * rprojW);
                    ctx.closePath();
                    if (d.fillColor) { ctx.fillStyle = d.fillColor; ctx.fill(); }
                    ctx.stroke();
                }
            } else {
                // Preview: just the A→B edge
                ctx.beginPath();
                ctx.moveTo(p1.x, p1.y);
                ctx.lineTo(p2.x, p2.y);
                ctx.stroke();
            }
        }
    } else if (d.type === 'path' || d.type === 'polyline') {
        // Path (closed) or Polyline (open) — multi-point
        var mpts = d.points;
        if (mpts && mpts.length > 1) {
            ctx.beginPath();
            var mp0 = _tvToPixel(chartId, mpts[0].t, mpts[0].p);
            if (mp0) {
                ctx.moveTo(mp0.x, mp0.y);
                for (var mi = 1; mi < mpts.length; mi++) {
                    var mpi = _tvToPixel(chartId, mpts[mi].t, mpts[mi].p);
                    if (mpi) ctx.lineTo(mpi.x, mpi.y);
                }
                if (d.type === 'path') ctx.closePath();
                if (d.fillColor && d.type === 'path') { ctx.fillStyle = d.fillColor; ctx.fill(); }
                ctx.stroke();
            }
        }
    } else if (d.type === 'shape_arc') {
        // Arc: 3-point (start, end, control for curvature)
        if (p1 && p2) {
            var sap3 = d.t3 !== undefined ? _tvToPixel(chartId, d.t3, d.p3) : null;
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            if (sap3) {
                ctx.quadraticCurveTo(sap3.x, sap3.y, p2.x, p2.y);
            } else {
                ctx.lineTo(p2.x, p2.y);
            }
            ctx.stroke();
        }
    } else if (d.type === 'curve') {
        // Curve: 2-point with auto control point (arc above midpoint)
        if (p1 && p2) {
            var ccx = (p1.x + p2.x) / 2, ccy = Math.min(p1.y, p2.y) - Math.abs(p2.x - p1.x) * 0.3;
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.quadraticCurveTo(ccx, ccy, p2.x, p2.y);
            ctx.stroke();
        }
    } else if (d.type === 'double_curve') {
        // Double Curve: 3-point S-curve (A→mid via C, mid→B via opposite)
        if (p1 && p2) {
            var dcp3 = d.t3 !== undefined ? _tvToPixel(chartId, d.t3, d.p3) : null;
            var dcMidX = (p1.x + p2.x) / 2, dcMidY = (p1.y + p2.y) / 2;
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            if (dcp3) {
                ctx.quadraticCurveTo(dcp3.x, dcp3.y, dcMidX, dcMidY);
                // Mirror control point for second half
                var dMirX = 2 * dcMidX - dcp3.x, dMirY = 2 * dcMidY - dcp3.y;
                ctx.quadraticCurveTo(dMirX, dMirY, p2.x, p2.y);
            } else {
                ctx.lineTo(p2.x, p2.y);
            }
            ctx.stroke();
        }
    } else if (d.type === 'long_position' || d.type === 'short_position') {
        // Long/Short Position: entry line, target (profit) and stop-loss zones
        if (p1 && p2) {
            var isLong = d.type === 'long_position';
            var entryY = p1.y, targetY = p2.y;
            var leftX = Math.min(p1.x, p2.x), rightX = Math.max(p1.x, p2.x);
            if (rightX - leftX < 20) rightX = leftX + 150;
            // Determine stop: mirror of target across entry
            var stopY = entryY + (entryY - targetY);
            // Profit zone (green)
            var profTop = Math.min(entryY, targetY), profBot = Math.max(entryY, targetY);
            ctx.fillStyle = isLong ? 'rgba(38,166,91,0.25)' : 'rgba(239,83,80,0.25)';
            ctx.fillRect(leftX, profTop, rightX - leftX, profBot - profTop);
            // Stop zone (red)
            var stopTop = Math.min(entryY, stopY), stopBot = Math.max(entryY, stopY);
            ctx.fillStyle = isLong ? 'rgba(239,83,80,0.25)' : 'rgba(38,166,91,0.25)';
            ctx.fillRect(leftX, stopTop, rightX - leftX, stopBot - stopTop);
            // Entry line
            ctx.setLineDash([]);
            ctx.beginPath();
            ctx.moveTo(leftX, entryY); ctx.lineTo(rightX, entryY);
            ctx.stroke();
            // Target and stop lines (dashed)
            ctx.setLineDash([4, 3]);
            ctx.beginPath();
            ctx.moveTo(leftX, targetY); ctx.lineTo(rightX, targetY);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(leftX, stopY); ctx.lineTo(rightX, stopY);
            ctx.stroke();
            ctx.setLineDash([]);
            // Labels
            ctx.fillStyle = col;
            ctx.font = '11px sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText(isLong ? 'Target' : 'Stop', leftX + 4, targetY - 4);
            ctx.fillText('Entry', leftX + 4, entryY - 4);
            ctx.fillText(isLong ? 'Stop' : 'Target', leftX + 4, stopY - 4);
        }
    } else if (d.type === 'forecast') {
        // Forecast: solid line for history, dashed fan lines for projection
        if (p1 && p2) {
            // Solid history segment
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
            // Dashed projection lines — fan of 3 paths
            var fdx = p2.x - p1.x, fdy = p2.y - p1.y;
            ctx.setLineDash([6, 4]);
            var fAngles = [-0.3, 0, 0.3];
            for (var fi = 0; fi < fAngles.length; fi++) {
                var fAngle = Math.atan2(fdy, fdx) + fAngles[fi];
                var fLen = Math.sqrt(fdx * fdx + fdy * fdy);
                ctx.beginPath();
                ctx.moveTo(p2.x, p2.y);
                ctx.lineTo(p2.x + fLen * Math.cos(fAngle), p2.y + fLen * Math.sin(fAngle));
                ctx.stroke();
            }
            ctx.setLineDash([]);
        }
    } else if (d.type === 'bars_pattern') {
        // Bars Pattern: source region box with dashed projected copy
        if (p1 && p2) {
            var bpW = Math.abs(p2.x - p1.x), bpH = Math.abs(p2.y - p1.y);
            var bpL = Math.min(p1.x, p2.x), bpT = Math.min(p1.y, p2.y);
            ctx.strokeRect(bpL, bpT, bpW, bpH);
            ctx.setLineDash([4, 3]);
            ctx.strokeRect(bpL + bpW, bpT, bpW, bpH);
            ctx.setLineDash([]);
        }
    } else if (d.type === 'ghost_feed') {
        // Ghost Feed: solid source segment, dashed continuation
        if (p1 && p2) {
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
            var gfdx = p2.x - p1.x, gfdy = p2.y - p1.y;
            ctx.setLineDash([5, 4]);
            ctx.globalAlpha = 0.5;
            ctx.beginPath();
            ctx.moveTo(p2.x, p2.y); ctx.lineTo(p2.x + gfdx, p2.y + gfdy);
            ctx.stroke();
            ctx.globalAlpha = 1.0;
            ctx.setLineDash([]);
        }
    } else if (d.type === 'projection') {
        // Projection: source box with dashed projected box
        if (p1 && p2) {
            var prjW = Math.abs(p2.x - p1.x), prjH = Math.abs(p2.y - p1.y);
            var prjL = Math.min(p1.x, p2.x), prjT = Math.min(p1.y, p2.y);
            ctx.setLineDash([]);
            ctx.strokeRect(prjL, prjT, prjW, prjH);
            ctx.setLineDash([4, 3]);
            ctx.strokeRect(prjL + prjW + 4, prjT, prjW, prjH);
            ctx.setLineDash([]);
            // Connecting arrow
            ctx.beginPath();
            ctx.moveTo(prjL + prjW, prjT + prjH / 2);
            ctx.lineTo(prjL + prjW + 4, prjT + prjH / 2);
            ctx.stroke();
        }
    } else if (d.type === 'anchored_vwap') {
        // Anchored VWAP: vertical anchor line + horizontal price label
        if (p1) {
            var avH = ctx.canvas.height;
            ctx.setLineDash([4, 3]);
            ctx.beginPath();
            ctx.moveTo(p1.x, 0); ctx.lineTo(p1.x, avH);
            ctx.stroke();
            ctx.setLineDash([]);
            // Label
            ctx.fillStyle = col;
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('VWAP', p1.x, 14);
        }
    } else if (d.type === 'fixed_range_vol') {
        // Fixed Range Volume Profile: vertical range with histogram placeholder
        if (p1 && p2) {
            var frL = Math.min(p1.x, p2.x), frR = Math.max(p1.x, p2.x);
            var frT = Math.min(p1.y, p2.y), frB = Math.max(p1.y, p2.y);
            ctx.setLineDash([4, 3]);
            ctx.beginPath();
            ctx.moveTo(frL, frT); ctx.lineTo(frL, frB);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(frR, frT); ctx.lineTo(frR, frB);
            ctx.stroke();
            ctx.setLineDash([]);
            // Horizontal bars placeholder
            ctx.fillStyle = 'rgba(41,98,255,0.2)';
            var frRows = 6, frRH = (frB - frT) / frRows;
            for (var fri = 0; fri < frRows; fri++) {
                var frW = (frR - frL) * (0.3 + Math.random() * 0.6);
                ctx.fillRect(frL, frT + fri * frRH + 1, frW, frRH - 2);
            }
        }
    } else if (d.type === 'price_range') {
        // Price Range: two horizontal lines with vertical connector and price diff label
        if (p1 && p2) {
            var prW = ctx.canvas.width;
            ctx.setLineDash([4, 3]);
            ctx.beginPath();
            ctx.moveTo(0, p1.y); ctx.lineTo(prW, p1.y);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(0, p2.y); ctx.lineTo(prW, p2.y);
            ctx.stroke();
            ctx.setLineDash([]);
            // Vertical connector
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y); ctx.lineTo(p1.x, p2.y);
            ctx.stroke();
            // Price diff label
            var prDiff = d.p2 !== undefined ? Math.abs(d.p2 - d.p1).toFixed(2) : '';
            ctx.fillStyle = col;
            ctx.font = '11px sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText(prDiff, p1.x + 6, (p1.y + p2.y) / 2 + 4);
        }
    } else if (d.type === 'date_range') {
        // Date Range: two vertical lines with horizontal connector
        if (p1 && p2) {
            var drH = ctx.canvas.height;
            ctx.setLineDash([4, 3]);
            ctx.beginPath();
            ctx.moveTo(p1.x, 0); ctx.lineTo(p1.x, drH);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(p2.x, 0); ctx.lineTo(p2.x, drH);
            ctx.stroke();
            ctx.setLineDash([]);
            // Horizontal connector at midY
            var drMidY = drH / 2;
            ctx.beginPath();
            ctx.moveTo(p1.x, drMidY); ctx.lineTo(p2.x, drMidY);
            ctx.stroke();
            // Arrow heads
            var drDir = p2.x > p1.x ? 1 : -1;
            ctx.beginPath();
            ctx.moveTo(p2.x, drMidY);
            ctx.lineTo(p2.x - drDir * 8, drMidY - 4);
            ctx.moveTo(p2.x, drMidY);
            ctx.lineTo(p2.x - drDir * 8, drMidY + 4);
            ctx.stroke();
        }
    } else if (d.type === 'date_price_range') {
        // Date and Price Range: rectangle region with dimension labels
        if (p1 && p2) {
            var dpLeft = Math.min(p1.x, p2.x), dpRight = Math.max(p1.x, p2.x);
            var dpTop = Math.min(p1.y, p2.y), dpBot = Math.max(p1.y, p2.y);
            ctx.fillStyle = 'rgba(41,98,255,0.1)';
            ctx.fillRect(dpLeft, dpTop, dpRight - dpLeft, dpBot - dpTop);
            ctx.strokeRect(dpLeft, dpTop, dpRight - dpLeft, dpBot - dpTop);
            // Price diff label
            var dpDiff = d.p2 !== undefined ? Math.abs(d.p2 - d.p1).toFixed(2) : '';
            ctx.fillStyle = col;
            ctx.font = '11px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(dpDiff, (dpLeft + dpRight) / 2, dpTop - 6);
        }
    }

    // Draw selection handles
    if (selected) {
        var anchors = _tvDrawAnchors(chartId, d);
        for (var ai = 0; ai < anchors.length; ai++) {
            var anc = anchors[ai];
            ctx.fillStyle = _cssVar('--pywry-draw-handle-fill');
            ctx.strokeStyle = col;
            ctx.lineWidth = 2;
            ctx.setLineDash([]);
            ctx.beginPath();
            ctx.arc(anc.x, anc.y, 5, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
        }
    }

    ctx.restore();
}

// Rounded rect helper
function _roundRect(ctx, x, y, w, h, r) {
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

