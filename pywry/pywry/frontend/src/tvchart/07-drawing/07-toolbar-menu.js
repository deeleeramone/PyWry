// ---- Floating edit toolbar ----
var _floatingToolbar = null;   // current DOM element
var _floatingChartId = null;
var _colorPickerEl = null;
var _widthPickerEl = null;

function _tvShowFloatingToolbar(chartId, drawIdx) {
    _tvHideFloatingToolbar();
    _tvHideContextMenu();
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds || drawIdx < 0 || drawIdx >= ds.drawings.length) return;
    var d = ds.drawings[drawIdx];

    var bar = document.createElement('div');
    bar.className = 'pywry-draw-toolbar';
    _floatingToolbar = bar;
    _floatingChartId = chartId;

    // Determine which controls are relevant for this drawing type
    var _arrowMarkers = ['arrow_marker', 'arrow_mark_up', 'arrow_mark_down', 'arrow_mark_left', 'arrow_mark_right'];
    var _hoverTextMarkers = ['pin', 'flag_mark', 'signpost'];
    var _filledMarkers = ['arrow_marker', 'arrow_mark_up', 'arrow_mark_down', 'arrow_mark_left', 'arrow_mark_right', 'anchored_text', 'note', 'price_note', 'pin', 'callout', 'comment', 'price_label', 'signpost', 'flag_mark'];
    var isArrowMarker = _arrowMarkers.indexOf(d.type) !== -1;
    var isHoverTextMarker = _hoverTextMarkers.indexOf(d.type) !== -1;
    var isFilledMarker = _filledMarkers.indexOf(d.type) !== -1;
    var hasLineStyle = d.type !== 'text' && d.type !== 'brush' && d.type !== 'measure' && !isFilledMarker;
    var hasLineWidth = d.type !== 'text' && !isFilledMarker;
    var hasColorSwatch = d.type !== 'measure' && !isArrowMarker && !isHoverTextMarker;

    // Arrow markers: fill / border / text icon buttons with color indicators
    if (isArrowMarker) {
        var fillBtn = _dtColorBtn(_DT_ICONS.bucket, 'Fill color',
            d.fillColor || d.color || _drawDefaults.color, function(e) {
            _tvToggleColorPicker(chartId, drawIdx, fillBtn._indicator, 'fillColor');
        });
        bar.appendChild(fillBtn);

        var borderBtn = _dtColorBtn(_DT_ICONS.border, 'Border color',
            d.borderColor || d.color || _drawDefaults.color, function(e) {
            _tvToggleColorPicker(chartId, drawIdx, borderBtn._indicator, 'borderColor');
        });
        bar.appendChild(borderBtn);

        var textBtn = _dtColorBtn(_DT_ICONS.text, 'Text color',
            d.textColor || d.color || _drawDefaults.color, function(e) {
            _tvToggleColorPicker(chartId, drawIdx, textBtn._indicator, 'textColor');
        });
        bar.appendChild(textBtn);
        bar.appendChild(_dtSep());
    }

    // Pin / Flag / Signpost: pencil + color indicator, T, font size, settings, lock, trash, more
    if (isHoverTextMarker) {
        var htColorBtn = _dtColorBtn(_DT_ICONS.pencil, 'Color',
            d.markerColor || d.color || _drawDefaults.color, function(e) {
            _tvToggleColorPicker(chartId, drawIdx, htColorBtn._indicator, 'markerColor');
        });
        bar.appendChild(htColorBtn);

        var htTextBtn = _dtColorBtn(_DT_ICONS.text, 'Text',
            d.color || _drawDefaults.color, function(e) {
            _tvToggleColorPicker(chartId, drawIdx, htTextBtn._indicator, 'color');
        });
        bar.appendChild(htTextBtn);

        var htFsLabel = document.createElement('span');
        htFsLabel.className = 'dt-label';
        htFsLabel.textContent = d.fontSize || 14;
        htFsLabel.title = 'Font size';
        htFsLabel.addEventListener('click', function(e) {
            e.stopPropagation();
            _tvShowDrawingSettings(chartId, drawIdx);
        });
        bar.appendChild(htFsLabel);
        bar.appendChild(_dtSep());
    }

    // Color swatch (non-arrow-marker tools)
    if (hasColorSwatch) {
        var swatch = document.createElement('div');
        swatch.className = 'dt-swatch';
        swatch.style.background = d.color || _drawDefaults.color;
        swatch.title = 'Color';
        swatch.addEventListener('click', function(e) {
            e.stopPropagation();
            _tvToggleColorPicker(chartId, drawIdx, swatch);
        });
        bar.appendChild(swatch);
        bar.appendChild(_dtSep());
    }

    // Line width button
    if (hasLineWidth) {
        var lwBtn = _dtBtn(_DT_ICONS.lineW, 'Line width', function(e) {
            e.stopPropagation();
            _tvToggleWidthPicker(chartId, drawIdx, lwBtn);
        });
        var lwLabel = document.createElement('span');
        lwLabel.className = 'dt-label';
        lwLabel.textContent = (d.lineWidth || 2) + 'px';
        lwLabel.title = 'Line width';
        lwLabel.addEventListener('click', function(e) {
            e.stopPropagation();
            _tvToggleWidthPicker(chartId, drawIdx, lwBtn);
        });
        bar.appendChild(lwBtn);
        bar.appendChild(lwLabel);
        bar.appendChild(_dtSep());
    }

    // Line style cycle (solid → dashed → dotted)
    if (hasLineStyle) {
        var styleBtn = _dtBtn(_DT_ICONS.pencil, 'Line style', function() {
            d.lineStyle = ((d.lineStyle || 0) + 1) % 3;
            _tvRenderDrawings(chartId);
        });
        bar.appendChild(styleBtn);
        bar.appendChild(_dtSep());
    }

    // Lock toggle
    var lockBtn = _dtBtn(d.locked ? _DT_ICONS.lock : _DT_ICONS.unlock,
        d.locked ? 'Unlock' : 'Lock', function() {
        d.locked = !d.locked;
        lockBtn.innerHTML = d.locked ? _DT_ICONS.lock : _DT_ICONS.unlock;
        lockBtn.title = d.locked ? 'Unlock' : 'Lock';
        if (d.locked) lockBtn.classList.add('active');
        else lockBtn.classList.remove('active');
    });
    if (d.locked) lockBtn.classList.add('active');
    bar.appendChild(lockBtn);

    bar.appendChild(_dtSep());

    // Settings button — opens drawing settings panel for any type
    var settingsBtn = _dtBtn(_DT_ICONS.settings, 'Settings', function() {
        _tvShowDrawingSettings(chartId, drawIdx);
    });
    bar.appendChild(settingsBtn);
    bar.appendChild(_dtSep());

    // Delete
    var delBtn = _dtBtn(_DT_ICONS.trash, 'Delete', function() {
        _tvDeleteDrawing(chartId, drawIdx);
    });
    delBtn.style.color = _cssVar('--pywry-draw-danger', '#f44336');
    bar.appendChild(delBtn);

    bar.appendChild(_dtSep());

    // More (...)
    var moreBtn = _dtBtn(_DT_ICONS.more, 'More', function(e) {
        e.stopPropagation();
        // Show context menu near toolbar
        var rect = bar.getBoundingClientRect();
        var cRect = ds.canvas.getBoundingClientRect();
        _tvShowContextMenu(chartId, drawIdx,
            rect.right - cRect.left, rect.bottom - cRect.top + 4);
    });
    bar.appendChild(moreBtn);

    ds.uiLayer.appendChild(bar);
    _tvRepositionToolbar(chartId);
}

function _tvRepositionToolbar(chartId) {
    if (!_floatingToolbar || _floatingChartId !== chartId) return;
    if (_drawSelectedIdx < 0) { _tvHideFloatingToolbar(); return; }
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds || _drawSelectedIdx >= ds.drawings.length) { _tvHideFloatingToolbar(); return; }
    var d = ds.drawings[_drawSelectedIdx];
    var anchors = _tvDrawAnchors(chartId, d);
    if (anchors.length === 0) { _tvHideFloatingToolbar(); return; }

    // Position above the topmost anchor
    var minY = Infinity, midX = 0;
    for (var i = 0; i < anchors.length; i++) {
        if (anchors[i].y < minY) minY = anchors[i].y;
        midX += anchors[i].x;
    }
    midX /= anchors.length;

    var tbW = _floatingToolbar.offsetWidth || 300;
    var left = midX - tbW / 2;
    var top  = minY - 44;
    // Clamp to container
    var cw = ds.canvas.clientWidth;
    if (left < 4) left = 4;
    if (left + tbW > cw - 4) left = cw - tbW - 4;
    if (top < 4) top = 4;

    _floatingToolbar.style.left = left + 'px';
    _floatingToolbar.style.top  = top  + 'px';
}

function _tvHideFloatingToolbar() {
    if (_floatingToolbar && _floatingToolbar.parentNode) {
        _floatingToolbar.parentNode.removeChild(_floatingToolbar);
    }
    _floatingToolbar = null;
    _floatingChartId = null;
    _tvHideColorPicker();
    _tvHideWidthPicker();
}

function _dtBtn(svgHtml, title, onclick) {
    var btn = document.createElement('button');
    btn.innerHTML = svgHtml;
    btn.title = title;
    btn.addEventListener('click', function(e) { e.stopPropagation(); onclick(e); });
    return btn;
}

/**
 * Create a toolbar button with an icon and a color indicator bar beneath it.
 * Used for fill / border / text color controls on filled marker drawings.
 */
function _dtColorBtn(svgHtml, title, color, onclick) {
    var btn = document.createElement('button');
    btn.className = 'dt-color-btn';
    btn.title = title;
    btn.innerHTML = svgHtml;
    var indicator = document.createElement('span');
    indicator.className = 'dt-color-indicator';
    indicator.style.background = color;
    btn.appendChild(indicator);
    btn.addEventListener('click', function(e) { e.stopPropagation(); onclick(e); });
    btn._indicator = indicator;
    return btn;
}

function _dtSep() {
    var s = document.createElement('div');
    s.className = 'dt-sep';
    return s;
}

// ---- HSV / RGB conversion helpers ----
function _hsvToRgb(h, s, v) {
    var i = Math.floor(h * 6), f = h * 6 - i, p = v * (1 - s);
    var q = v * (1 - f * s), t = v * (1 - (1 - f) * s);
    var r, g, b;
    switch (i % 6) {
        case 0: r = v; g = t; b = p; break;
        case 1: r = q; g = v; b = p; break;
        case 2: r = p; g = v; b = t; break;
        case 3: r = p; g = q; b = v; break;
        case 4: r = t; g = p; b = v; break;
        case 5: r = v; g = p; b = q; break;
    }
    return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
}

function _rgbToHsv(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    var max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
    var h = 0, s = max === 0 ? 0 : d / max, v = max;
    if (d !== 0) {
        switch (max) {
            case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
            case g: h = ((b - r) / d + 2) / 6; break;
            case b: h = ((r - g) / d + 4) / 6; break;
        }
    }
    return [h, s, v];
}

function _hexToRgb(hex) {
    hex = hex.replace(/^#/, '');
    if (hex.length === 3) hex = hex[0]+hex[0]+hex[1]+hex[1]+hex[2]+hex[2];
    var n = parseInt(hex, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function _rgbToHex(r, g, b) {
    return '#' + ((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1);
}

// ---- Canvas paint helpers for color picker ----
function _cpPaintSV(canvas, hue) {
    var w = canvas.width, h = canvas.height;
    var ctx = canvas.getContext('2d');
    var hRgb = _hsvToRgb(hue, 1, 1);
    var hHex = _rgbToHex(hRgb[0], hRgb[1], hRgb[2]);
    ctx.fillStyle = _cssVar('--pywry-cp-sv-white', '#ffffff');
    ctx.fillRect(0, 0, w, h);
    var gH = ctx.createLinearGradient(0, 0, w, 0);
    gH.addColorStop(0, _cssVar('--pywry-cp-sv-white', '#ffffff'));
    gH.addColorStop(1, hHex);
    ctx.fillStyle = gH;
    ctx.fillRect(0, 0, w, h);
    var gV = ctx.createLinearGradient(0, 0, 0, h);
    var svBlack = _cssVar('--pywry-cp-sv-black', '#000000');
    var svRgb = _hexToRgb(svBlack);
    gV.addColorStop(0, 'rgba(' + svRgb[0] + ',' + svRgb[1] + ',' + svRgb[2] + ',0)');
    gV.addColorStop(1, svBlack);
    ctx.fillStyle = gV;
    ctx.fillRect(0, 0, w, h);
}

function _cpPaintHue(canvas) {
    var w = canvas.width, h = canvas.height;
    var ctx = canvas.getContext('2d');
    var g = ctx.createLinearGradient(0, 0, w, 0);
    g.addColorStop(0,     _cssVar('--pywry-cp-hue-0', '#ff0000'));
    g.addColorStop(0.167, _cssVar('--pywry-cp-hue-1', '#ffff00'));
    g.addColorStop(0.333, _cssVar('--pywry-cp-hue-2', '#00ff00'));
    g.addColorStop(0.5,   _cssVar('--pywry-cp-hue-3', '#00ffff'));
    g.addColorStop(0.667, _cssVar('--pywry-cp-hue-4', '#0000ff'));
    g.addColorStop(0.833, _cssVar('--pywry-cp-hue-5', '#ff00ff'));
    g.addColorStop(1,     _cssVar('--pywry-cp-hue-6', '#ff0000'));
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
}

// ---- Full color picker popup (canvas-based, all inline styles) ----
function _tvToggleColorPicker(chartId, drawIdx, anchor, propName) {
    _tvHideWidthPicker();
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds) return;
    var d = ds.drawings[drawIdx];
    var _cpProp = propName || 'color';
    var curHex = _tvColorToHex(d[_cpProp] || d.color || _drawDefaults.color, _drawDefaults.color);
    var curOpacity = _tvToNumber(d[_cpProp + 'Opacity'], _tvColorOpacityPercent(d[_cpProp], 100));

    _tvShowColorOpacityPopup(anchor, curHex, curOpacity, null, function(newColor, newOpacity) {
        d[_cpProp] = _tvColorWithOpacity(newColor, newOpacity, newColor);
        d[_cpProp + 'Opacity'] = newOpacity;
        anchor.style.background = _tvColorWithOpacity(newColor, newOpacity, newColor);
        if (d.type === 'hline') _tvSyncPriceLineColor(chartId, drawIdx, _tvColorWithOpacity(newColor, newOpacity, newColor));
        _tvRenderDrawings(chartId);
    });
}

function _tvHideColorPicker() {
    if (_colorPickerEl && _colorPickerEl.parentNode) {
        _colorPickerEl.parentNode.removeChild(_colorPickerEl);
    }
    _colorPickerEl = null;
}

// ---- Width picker popup ----
function _tvToggleWidthPicker(chartId, drawIdx, anchor) {
    if (_widthPickerEl) { _tvHideWidthPicker(); return; }
    _tvHideColorPicker();
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds) return;
    var d = ds.drawings[drawIdx];
    var picker = document.createElement('div');
    picker.className = 'pywry-draw-width-picker';
    _widthPickerEl = picker;

    for (var i = 0; i < _DRAW_WIDTHS.length; i++) {
        (function(pw) {
            var row = document.createElement('div');
            row.className = 'wp-row' + ((d.lineWidth || 2) === pw ? ' sel' : '');
            var line = document.createElement('div');
            line.className = 'wp-line';
            line.style.borderTopWidth = pw + 'px';
            row.appendChild(line);
            var label = document.createElement('span');
            label.textContent = pw + 'px';
            row.appendChild(label);
            row.addEventListener('click', function(e) {
                e.stopPropagation();
                d.lineWidth = pw;
                _tvRenderDrawings(chartId);
                _tvHideWidthPicker();
                // Update label in toolbar
                var lbls = _floatingToolbar ? _floatingToolbar.querySelectorAll('.dt-label') : [];
                if (lbls.length > 0) lbls[0].textContent = pw + 'px';
            });
            picker.appendChild(row);
        })(_DRAW_WIDTHS[i]);
    }

    var _oc = _tvAppendOverlay(chartId, picker);

    // Position the picker relative to the anchor
    requestAnimationFrame(function() {
        var _cs = _tvContainerSize(_oc);
        var aRect = _tvContainerRect(_oc, anchor.getBoundingClientRect());
        var pH = picker.offsetHeight;
        var pW = picker.offsetWidth;
        var top = aRect.top - pH - 6;
        var left = aRect.left;
        if (top < 0) {
            top = aRect.bottom + 6;
        }
        if (left + pW > _cs.width - 4) {
            left = _cs.width - pW - 4;
        }
        if (left < 4) left = 4;
        picker.style.top = top + 'px';
        picker.style.left = left + 'px';
    });
}

function _tvHideWidthPicker() {
    if (_widthPickerEl && _widthPickerEl.parentNode) {
        _widthPickerEl.parentNode.removeChild(_widthPickerEl);
    }
    _widthPickerEl = null;
}

// ---- Context menu (right-click on drawing) ----
var _ctxMenuEl = null;

function _tvShowContextMenu(chartId, drawIdx, posX, posY) {
    _tvHideContextMenu();
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds || drawIdx < 0 || drawIdx >= ds.drawings.length) return;
    var d = ds.drawings[drawIdx];

    var menu = document.createElement('div');
    menu.className = 'pywry-draw-ctx-menu';
    _ctxMenuEl = menu;

    // Settings
    _cmItem(menu, _DT_ICONS.settings, 'Settings...', '', function() {
        _tvHideContextMenu();
        _tvShowDrawingSettings(chartId, drawIdx);
    });

    _cmSep(menu);

    // Clone
    _cmItem(menu, _DT_ICONS.clone, 'Clone', 'Ctrl+Drag', function() {
        var copy = Object.assign({}, d);
        copy._id = ++_drawIdCounter;
        ds.drawings.push(copy);
        _emitDrawingAdded(chartId, copy);
        _tvRenderDrawings(chartId);
        _tvHideContextMenu();
    });

    // Copy (as JSON to clipboard)
    _cmItem(menu, '', 'Copy', 'Ctrl+C', function() {
        try {
            navigator.clipboard.writeText(JSON.stringify(d));
        } catch(e) {}
        _tvHideContextMenu();
    });

    _cmSep(menu);

    // Hide / Show
    var isHidden = d.hidden;
    _cmItem(menu, isHidden ? _DT_ICONS.eye : _DT_ICONS.eyeOff,
        isHidden ? 'Show' : 'Hide', '', function() {
        d.hidden = !d.hidden;
        if (d.hidden) {
            _drawSelectedIdx = -1;
            _tvHideFloatingToolbar();
        }
        _tvRenderDrawings(chartId);
        _tvHideContextMenu();
    });

    _cmSep(menu);

    // Bring to front
    _cmItem(menu, '', 'Bring to Front', '', function() {
        var _undoChartId = chartId;
        var _undoFromIdx = drawIdx;
        _tvPushUndo({
            label: 'Bring to front',
            undo: function() {
                var ds2 = window.__PYWRY_DRAWINGS__[_undoChartId];
                if (!ds2 || ds2.drawings.length === 0) return;
                // Move last back to original index
                var item = ds2.drawings.pop();
                ds2.drawings.splice(_undoFromIdx, 0, item);
                _tvDeselectAll(_undoChartId);
            },
            redo: function() {
                var ds2 = window.__PYWRY_DRAWINGS__[_undoChartId];
                if (!ds2 || _undoFromIdx >= ds2.drawings.length) return;
                ds2.drawings.push(ds2.drawings.splice(_undoFromIdx, 1)[0]);
                _tvDeselectAll(_undoChartId);
            },
        });
        ds.drawings.push(ds.drawings.splice(drawIdx, 1)[0]);
        _drawSelectedIdx = ds.drawings.length - 1;
        _tvRenderDrawings(chartId);
        _tvHideContextMenu();
    });

    // Send to back
    _cmItem(menu, '', 'Send to Back', '', function() {
        ds.drawings.unshift(ds.drawings.splice(drawIdx, 1)[0]);
        _drawSelectedIdx = 0;
        _tvRenderDrawings(chartId);
        _tvHideContextMenu();
    });

    _cmSep(menu);

    // Delete
    _cmItem(menu, _DT_ICONS.trash, 'Delete', 'Del', function() {
        _tvDeleteDrawing(chartId, drawIdx);
        _tvHideContextMenu();
    }, true);

    menu.style.left = posX + 'px';
    menu.style.top  = posY + 'px';
    ds.uiLayer.appendChild(menu);

    // Clamp context menu within container
    requestAnimationFrame(function() {
        var mRect = menu.getBoundingClientRect();
        var uiRect = ds.uiLayer.getBoundingClientRect();
        if (mRect.right > uiRect.right) {
            menu.style.left = Math.max(0, posX - (mRect.right - uiRect.right)) + 'px';
        }
        if (mRect.bottom > uiRect.bottom) {
            menu.style.top = Math.max(0, posY - (mRect.bottom - uiRect.bottom)) + 'px';
        }
    });

    // Close on click outside
    setTimeout(function() {
        document.addEventListener('click', _ctxMenuOutsideClick, { once: true });
    }, 0);
}

function _ctxMenuOutsideClick() { _tvHideContextMenu(); }

function _tvHideContextMenu() {
    if (_ctxMenuEl && _ctxMenuEl.parentNode) {
        _ctxMenuEl.parentNode.removeChild(_ctxMenuEl);
    }
    _ctxMenuEl = null;
}

function _cmItem(menu, icon, label, shortcut, onclick, danger) {
    var row = document.createElement('div');
    row.className = 'cm-item' + (danger ? ' cm-danger' : '');
    
    // Icon container (always present for consistent spacing)
    var iconWrap = document.createElement('span');
    iconWrap.className = 'cm-icon';
    if (icon) iconWrap.innerHTML = icon;
    row.appendChild(iconWrap);
    
    // Label
    var lbl = document.createElement('span');
    lbl.className = 'cm-label';
    lbl.textContent = label;
    row.appendChild(lbl);
    
    // Shortcut
    if (shortcut) {
        var sc = document.createElement('span');
        sc.className = 'cm-shortcut';
        sc.textContent = shortcut;
        row.appendChild(sc);
    }
    
    row.addEventListener('click', function(e) { e.stopPropagation(); onclick(); });
    menu.appendChild(row);
}

function _cmSep(menu) {
    var s = document.createElement('div');
    s.className = 'cm-sep';
    menu.appendChild(s);
}

// ---- Delete drawing helper ----
