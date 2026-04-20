// ---------------------------------------------------------------------------
// Shared color+opacity picker popup — used by all settings modals
// ---------------------------------------------------------------------------
var _colorOpacityPopupEl = null;
var _colorOpacityCleanups = [];

function _tvHideColorOpacityPopup() {
    for (var i = 0; i < _colorOpacityCleanups.length; i++) {
        try { _colorOpacityCleanups[i](); } catch(e) {}
    }
    _colorOpacityCleanups = [];
    if (_colorOpacityPopupEl && _colorOpacityPopupEl.parentNode) {
        _colorOpacityPopupEl.parentNode.removeChild(_colorOpacityPopupEl);
    }
    _colorOpacityPopupEl = null;
}

/**
 * Show a color+opacity popup anchored to `anchor`.
 * @param {Element} anchor       The element to position relative to
 * @param {string}  currentColor Hex color
 * @param {number}  currentOpacity 0-100 percent
 * @param {Element} parentOverlay The overlay to append the popup to (or document.body)
 * @param {function(color,opacity)} onUpdate Called on every change
 */
function _tvShowColorOpacityPopup(anchor, currentColor, currentOpacity, parentOverlay, onUpdate) {
    if (!anchor) return;
    if (_colorOpacityPopupEl && _colorOpacityPopupEl._anchor === anchor) {
        _tvHideColorOpacityPopup();
        return;
    }
    _tvHideColorOpacityPopup();
    _tvHideColorPicker();

    currentColor = _tvColorToHex(currentColor || '#aeb4c2', '#aeb4c2');
    currentOpacity = _tvClamp(_tvToNumber(currentOpacity, 100), 0, 100);

    var curRgb = _hexToRgb(currentColor);
    var curHsv = _rgbToHsv(curRgb[0], curRgb[1], curRgb[2]);
    var cpH = curHsv[0], cpS = curHsv[1], cpV = curHsv[2];

    var PW = 276;
    var popup = document.createElement('div');
    popup.style.cssText =
        'position:fixed;z-index:12002;width:' + PW + 'px;padding:14px;' +
        'background:' + _cssVar('--pywry-draw-bg', '#1e222d') + ';' +
        'border:1px solid ' + _cssVar('--pywry-draw-border', '#434651') + ';' +
        'border-radius:12px;box-shadow:0 12px 32px ' + _cssVar('--pywry-draw-shadow-lg', 'rgba(0,0,0,.6)') + ';' +
        'font-family:-apple-system,BlinkMacSystemFont,sans-serif;';
    popup.addEventListener('click', function(e) { e.stopPropagation(); });
    popup.addEventListener('mousedown', function(e) { e.stopPropagation(); });
    popup._anchor = anchor;

    var presets = _getDrawColors();
    var presetButtons = [];

    // === SV Canvas ===
    var svW = PW, svH = 150;
    var svWrap = document.createElement('div');
    svWrap.style.cssText =
        'position:relative;width:' + svW + 'px;height:' + svH + 'px;' +
        'border-radius:6px;overflow:hidden;cursor:crosshair;margin-bottom:10px;';
    var svCanvas = document.createElement('canvas');
    svCanvas.width = svW * 2; svCanvas.height = svH * 2;
    svCanvas.style.cssText = 'width:100%;height:100%;display:block;';
    svWrap.appendChild(svCanvas);

    var svDot = document.createElement('div');
    svDot.style.cssText =
        'position:absolute;width:14px;height:14px;border-radius:50%;' +
        'border:2px solid ' + _cssVar('--pywry-draw-handle-fill', '#ffffff') + ';' +
        'box-shadow:0 0 4px ' + _cssVar('--pywry-draw-shadow-lg', 'rgba(0,0,0,.6)') + ';' +
        'pointer-events:none;transform:translate(-50%,-50%);';
    svWrap.appendChild(svDot);
    popup.appendChild(svWrap);

    function paintSV() { _cpPaintSV(svCanvas, cpH); }

    function svFromEvent(e) {
        var r = svWrap.getBoundingClientRect();
        cpS = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
        cpV = Math.max(0, Math.min(1, 1 - (e.clientY - r.top) / r.height));
        applyFromHSV();
    }
    svWrap.addEventListener('mousedown', function(e) {
        e.preventDefault();
        svFromEvent(e);
        function mv(ev) { svFromEvent(ev); }
        function up() { document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); }
        document.addEventListener('mousemove', mv);
        document.addEventListener('mouseup', up);
    });

    // === Hue bar ===
    var hueH = 14;
    var hueWrap = document.createElement('div');
    hueWrap.style.cssText =
        'position:relative;width:100%;height:' + hueH + 'px;' +
        'border-radius:7px;overflow:hidden;cursor:pointer;margin-bottom:10px;';
    var hueCanvas = document.createElement('canvas');
    hueCanvas.width = svW * 2; hueCanvas.height = hueH * 2;
    hueCanvas.style.cssText = 'width:100%;height:100%;display:block;';
    hueWrap.appendChild(hueCanvas);
    _cpPaintHue(hueCanvas);

    var hueThumb = document.createElement('div');
    hueThumb.style.cssText =
        'position:absolute;top:50%;width:16px;height:16px;border-radius:50%;' +
        'border:2px solid ' + _cssVar('--pywry-draw-handle-fill', '#ffffff') + ';' +
        'box-shadow:0 0 4px ' + _cssVar('--pywry-draw-shadow-lg', 'rgba(0,0,0,.6)') + ';' +
        'pointer-events:none;transform:translate(-50%,-50%);';
    hueWrap.appendChild(hueThumb);
    popup.appendChild(hueWrap);

    function hueFromEvent(e) {
        var r = hueWrap.getBoundingClientRect();
        cpH = Math.max(0, Math.min(0.999, (e.clientX - r.left) / r.width));
        paintSV();
        applyFromHSV();
    }
    hueWrap.addEventListener('mousedown', function(e) {
        e.preventDefault();
        hueFromEvent(e);
        function mv(ev) { hueFromEvent(ev); }
        function up() { document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); }
        document.addEventListener('mousemove', mv);
        document.addEventListener('mouseup', up);
    });

    // === Hex input row ===
    var hexRow = document.createElement('div');
    hexRow.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:10px;';
    var prevBox = document.createElement('div');
    prevBox.style.cssText =
        'width:32px;height:32px;border-radius:4px;flex-shrink:0;' +
        'border:1px solid ' + _cssVar('--pywry-draw-border', '#434651') + ';';
    var hexIn = document.createElement('input');
    hexIn.type = 'text'; hexIn.spellcheck = false; hexIn.maxLength = 7;
    hexIn.style.cssText =
        'flex:1;background:' + _cssVar('--pywry-draw-input-bg', '#0a0a0d') + ';' +
        'border:1px solid ' + _cssVar('--pywry-draw-border', '#434651') + ';border-radius:4px;' +
        'color:' + _cssVar('--pywry-draw-input-text', '#d1d4dc') + ';font-size:13px;padding:6px 8px;font-family:monospace;' +
        'outline:none;text-transform:uppercase;';
    hexIn.addEventListener('focus', function() { hexIn.style.borderColor = _cssVar('--pywry-draw-input-focus', '#2962ff'); });
    hexIn.addEventListener('blur',  function() { hexIn.style.borderColor = _cssVar('--pywry-draw-border', '#434651'); });
    hexIn.addEventListener('keydown', function(e) {
        e.stopPropagation();
        if (e.key === 'Enter') {
            var val = hexIn.value.trim();
            if (val[0] !== '#') val = '#' + val;
            if (/^#[0-9a-fA-F]{6}$/.test(val)) {
                var rgb = _hexToRgb(val);
                var hsv = _rgbToHsv(rgb[0], rgb[1], rgb[2]);
                cpH = hsv[0]; cpS = hsv[1]; cpV = hsv[2];
                paintSV();
                applyFromHSV();
            }
        }
    });
    hexRow.appendChild(prevBox);
    hexRow.appendChild(hexIn);
    popup.appendChild(hexRow);

    // === Separator ===
    var sep1 = document.createElement('div');
    sep1.style.cssText = 'height:1px;background:' + _cssVar('--pywry-draw-border', '#434651') + ';margin:0 0 10px 0;';
    popup.appendChild(sep1);

    // === Preset swatches ===
    var swatchGrid = document.createElement('div');
    swatchGrid.style.cssText = 'display:grid;grid-template-columns:repeat(10,minmax(0,1fr));gap:6px;margin-bottom:14px;';
    popup.appendChild(swatchGrid);

    for (var pi = 0; pi < presets.length; pi++) {
        (function(presetColor) {
            var presetButton = document.createElement('button');
            presetButton.type = 'button';
            presetButton.dataset.color = presetColor.toLowerCase();
            presetButton.style.cssText =
                'width:100%;aspect-ratio:1;border-radius:6px;cursor:pointer;box-sizing:border-box;' +
                'border:2px solid transparent;background:' + presetColor + ';';
            presetButton.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                var rgb = _hexToRgb(presetColor);
                var hsv = _rgbToHsv(rgb[0], rgb[1], rgb[2]);
                cpH = hsv[0]; cpS = hsv[1]; cpV = hsv[2];
                paintSV();
                applyFromHSV();
            });
            presetButtons.push(presetButton);
            swatchGrid.appendChild(presetButton);
        })(presets[pi]);
    }

    // === Separator ===
    var sep2 = document.createElement('div');
    sep2.style.cssText = 'height:1px;background:' + _cssVar('--pywry-draw-border', '#434651') + ';margin:0 0 14px 0;';
    popup.appendChild(sep2);

    // === Opacity ===
    var opacityTitle = document.createElement('div');
    opacityTitle.textContent = 'Opacity';
    opacityTitle.style.cssText = 'color:' + _cssVar('--pywry-tvchart-text', '#d1d4dc') + ';font-size:12px;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:8px;';
    popup.appendChild(opacityTitle);

    var opacityRow = document.createElement('div');
    opacityRow.style.cssText = 'display:flex;align-items:center;gap:10px;';
    var opacitySlider = document.createElement('input');
    opacitySlider.type = 'range';
    opacitySlider.className = 'tv-settings-slider';
    opacitySlider.min = '0';
    opacitySlider.max = '100';
    opacityRow.appendChild(opacitySlider);
    var opacityValue = document.createElement('input');
    opacityValue.type = 'number';
    opacityValue.className = 'ts-input ts-input-sm';
    opacityValue.min = '0';
    opacityValue.max = '100';
    opacityValue.addEventListener('keydown', function(e) { e.stopPropagation(); });
    opacityRow.appendChild(opacityValue);
    var opacityUnit = document.createElement('span');
    opacityUnit.className = 'tv-settings-unit';
    opacityUnit.textContent = '%';
    opacityRow.appendChild(opacityUnit);
    popup.appendChild(opacityRow);

    // === Refresh helpers ===
    function refreshPresetSelection() {
        presetButtons.forEach(function(btn) {
            btn.style.borderColor = btn.dataset.color === currentColor.toLowerCase()
                ? _cssVar('--pywry-draw-input-focus', '#2962ff')
                : 'transparent';
        });
    }

    function refreshHSVUI() {
        var rgb = _hsvToRgb(cpH, cpS, cpV);
        var hex = _rgbToHex(rgb[0], rgb[1], rgb[2]);
        svDot.style.left = (cpS * 100) + '%';
        svDot.style.top  = ((1 - cpV) * 100) + '%';
        svDot.style.background = hex;
        hueThumb.style.left = (cpH * 100) + '%';
        var hRgb = _hsvToRgb(cpH, 1, 1);
        hueThumb.style.background = _rgbToHex(hRgb[0], hRgb[1], hRgb[2]);
        hexIn.value = hex.toUpperCase();
        prevBox.style.background = _tvColorWithOpacity(hex, currentOpacity, hex);
    }

    function applyFromHSV() {
        var rgb = _hsvToRgb(cpH, cpS, cpV);
        currentColor = _rgbToHex(rgb[0], rgb[1], rgb[2]);
        opacitySlider.value = String(currentOpacity);
        opacityValue.value = String(currentOpacity);
        prevBox.style.background = _tvColorWithOpacity(currentColor, currentOpacity, currentColor);
        refreshHSVUI();
        refreshPresetSelection();
        if (onUpdate) onUpdate(currentColor, currentOpacity);
    }

    function applySelection(nextColor, nextOpacity) {
        currentColor = _tvColorToHex(nextColor || currentColor, currentColor);
        currentOpacity = _tvClamp(_tvToNumber(nextOpacity, currentOpacity), 0, 100);
        var rgb = _hexToRgb(currentColor);
        var hsv = _rgbToHsv(rgb[0], rgb[1], rgb[2]);
        cpH = hsv[0]; cpS = hsv[1]; cpV = hsv[2];
        paintSV();
        opacitySlider.value = String(currentOpacity);
        opacityValue.value = String(currentOpacity);
        prevBox.style.background = _tvColorWithOpacity(currentColor, currentOpacity, currentColor);
        refreshHSVUI();
        refreshPresetSelection();
        if (onUpdate) onUpdate(currentColor, currentOpacity);
    }

    opacitySlider.addEventListener('input', function() {
        applySelection(currentColor, opacitySlider.value);
    });
    opacityValue.addEventListener('input', function() {
        applySelection(currentColor, opacityValue.value);
    });

    _colorOpacityPopupEl = popup;
    var appendTarget = parentOverlay || document.body;
    appendTarget.appendChild(popup);
    paintSV();
    applySelection(currentColor, currentOpacity);

    // --- Position within the parent (absolute if inside overlay, fixed if body) ---
    if (parentOverlay) {
        popup.style.position = 'absolute';
        // Find the settings panel inside the overlay to constrain within it
        var constrainEl = parentOverlay.querySelector('.tv-settings-panel') || parentOverlay;
        var constrainRect = constrainEl.getBoundingClientRect();
        var overlayRect = parentOverlay.getBoundingClientRect();
        var anchorRect = anchor.getBoundingClientRect();
        var popupRect = popup.getBoundingClientRect();
        // Calculate position relative to the overlay
        var top = anchorRect.bottom - overlayRect.top + 6;
        // If it goes below the panel bottom, show above the anchor
        if (top + popupRect.height > constrainRect.bottom - overlayRect.top - 8) {
            top = anchorRect.top - overlayRect.top - popupRect.height - 6;
        }
        // Clamp to panel bounds vertically
        var minTop = constrainRect.top - overlayRect.top + 4;
        var maxTop = constrainRect.bottom - overlayRect.top - popupRect.height - 4;
        top = Math.max(minTop, Math.min(maxTop, top));
        var left = anchorRect.left - overlayRect.left;
        // Clamp to panel bounds horizontally
        var maxLeft = constrainRect.right - overlayRect.left - popupRect.width - 4;
        left = Math.max(constrainRect.left - overlayRect.left + 4, Math.min(maxLeft, left));
        popup.style.top = top + 'px';
        popup.style.left = left + 'px';
    } else {
        var anchorRect = anchor.getBoundingClientRect();
        var popupRect = popup.getBoundingClientRect();
        var top = anchorRect.bottom + 10;
        if (top + popupRect.height > window.innerHeight - 12) {
            top = Math.max(12, anchorRect.top - popupRect.height - 10);
        }
        var left = anchorRect.left;
        if (left + popupRect.width > window.innerWidth - 12) {
            left = Math.max(12, window.innerWidth - popupRect.width - 12);
        }
        popup.style.top = top + 'px';
        popup.style.left = left + 'px';
    }

    // --- Dismissal: Escape key and click outside ---
    function onEscKey(e) {
        if (e.key === 'Escape') {
            e.stopPropagation();
            _tvHideColorOpacityPopup();
        }
    }
    function onOutsideClick(e) {
        if (popup.contains(e.target) || e.target === anchor) return;
        _tvHideColorOpacityPopup();
    }
    document.addEventListener('keydown', onEscKey, true);
    // Delay the click listener so the current click doesn't immediately close it
    var _outsideTimer = setTimeout(function() {
        document.addEventListener('mousedown', onOutsideClick, true);
    }, 0);
    _colorOpacityCleanups.push(function() {
        clearTimeout(_outsideTimer);
        document.removeEventListener('keydown', onEscKey, true);
        document.removeEventListener('mousedown', onOutsideClick, true);
    });
}

var _DRAW_WIDTHS = [1, 2, 3, 4];

