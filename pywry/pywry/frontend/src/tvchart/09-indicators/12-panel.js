function _tvHideIndicatorsPanel() {
    if (_indicatorsOverlay && _indicatorsOverlay._escHandler) {
        document.removeEventListener('keydown', _indicatorsOverlay._escHandler, true);
    }
    if (_indicatorsOverlay && _indicatorsOverlay.parentNode) {
        _indicatorsOverlay.parentNode.removeChild(_indicatorsOverlay);
    }
    if (_indicatorsOverlayChartId) _tvSetChartInteractionLocked(_indicatorsOverlayChartId, false);
    _indicatorsOverlay = null;
    _indicatorsOverlayChartId = null;
    _tvRefreshLegendVisibility();
}

function _tvShowIndicatorsPanel(chartId) {
    _tvHideIndicatorsPanel();
    chartId = chartId || 'main';
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry) { var keys = Object.keys(window.__PYWRY_TVCHARTS__); if (keys.length) { chartId = keys[0]; entry = window.__PYWRY_TVCHARTS__[chartId]; } }
    if (!entry) return;

    var ds = window.__PYWRY_DRAWINGS__[chartId] || _tvEnsureDrawingLayer(chartId);
    if (!ds) return;

    var overlay = document.createElement('div');
    overlay.className = 'tv-indicators-overlay';
    _indicatorsOverlay = overlay;
    _indicatorsOverlayChartId = chartId;
    _tvSetChartInteractionLocked(chartId, true);
    _tvRefreshLegendVisibility();
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) _tvHideIndicatorsPanel();
    });
    overlay.addEventListener('mousedown', function(e) { e.stopPropagation(); });
    overlay.addEventListener('wheel', function(e) { e.stopPropagation(); });

    // Escape closes the panel.  Use capture so we catch the key
    // before the search input's own keydown handler stops propagation.
    overlay._escHandler = function(e) {
        if (e.key === 'Escape' || e.keyCode === 27) {
            e.preventDefault();
            e.stopPropagation();
            _tvHideIndicatorsPanel();
        }
    };
    document.addEventListener('keydown', overlay._escHandler, true);

    var panel = document.createElement('div');
    panel.className = 'tv-indicators-panel';
    overlay.appendChild(panel);

    // Header
    var header = document.createElement('div');
    header.className = 'tv-indicators-header';
    var title = document.createElement('h3');
    title.textContent = 'Indicators';
    header.appendChild(title);
    var closeBtn = document.createElement('button');
    closeBtn.className = 'tv-settings-close';
    closeBtn.innerHTML = '<svg viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>';
    closeBtn.addEventListener('click', function() { _tvHideIndicatorsPanel(); });
    header.appendChild(closeBtn);
    panel.appendChild(header);

    // Search
    var searchWrap = document.createElement('div');
    searchWrap.className = 'tv-indicators-search pywry-search-wrapper pywry-search-inline';
    searchWrap.style.position = 'relative';
    var searchIcon = document.createElement('span');
    searchIcon.className = 'pywry-search-icon';
    searchIcon.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0016 9.5 6.5 6.5 0 109.5 16a6.47 6.47 0 004.23-1.57l.27.28v.79L19 20.49 20.49 19 15.5 14zM9.5 14A4.5 4.5 0 119.5 5a4.5 4.5 0 010 9z"/></svg>';
    searchWrap.appendChild(searchIcon);
    var searchInp = document.createElement('input');
    searchInp.type = 'text';
    searchInp.className = 'pywry-search-input';
    searchInp.placeholder = 'Search';
    searchInp.addEventListener('keydown', function(e) { e.stopPropagation(); });
    searchWrap.appendChild(searchInp);
    panel.appendChild(searchWrap);

    // List
    var list = document.createElement('div');
    list.className = 'tv-indicators-list pywry-scroll-container';
    panel.appendChild(list);
    try {
        if (window.PYWRY_SCROLLBARS && typeof window.PYWRY_SCROLLBARS.setup === 'function') {
            window.PYWRY_SCROLLBARS.setup(list);
        }
    } catch(e) {}

    // Active indicators section
    function renderList(filter) {
        list.innerHTML = '';

        // Active indicators
        var activeKeys = Object.keys(_activeIndicators);
        if (activeKeys.length > 0) {
            var actSec = document.createElement('div');
            actSec.className = 'tv-indicators-section';
            actSec.textContent = 'ACTIVE';
            list.appendChild(actSec);

            var shown = {};
            for (var a = 0; a < activeKeys.length; a++) {
                var ai = _activeIndicators[activeKeys[a]];
                if (ai.group && shown[ai.group]) continue;
                if (ai.group) shown[ai.group] = true;

                (function(sid, info) {
                    var item = document.createElement('div');
                    item.className = 'tv-indicator-item';
                    var nameSpan = document.createElement('span');
                    nameSpan.className = 'ind-name';
                    // Extract base name (remove any trailing period in parentheses from the stored name)
                    var baseName = (info.name || '').replace(/\s*\(\d+\)\s*$/, '');
                    nameSpan.textContent = baseName + (info.period ? ' (' + info.period + ')' : '');
                    nameSpan.style.color = info.color;
                    item.appendChild(nameSpan);
                    var gearBtn = document.createElement('span');
                    gearBtn.innerHTML = '\u2699';
                    gearBtn.title = 'Settings';
                    gearBtn.style.cssText = 'cursor:pointer;font-size:14px;line-height:1;padding:0 3px;color:var(--pywry-tvchart-text-muted);border-radius:3px;';
                    gearBtn.addEventListener('mouseenter', function() { gearBtn.style.color = 'var(--pywry-tvchart-text)'; gearBtn.style.background = 'var(--pywry-tvchart-hover)'; });
                    gearBtn.addEventListener('mouseleave', function() { gearBtn.style.color = 'var(--pywry-tvchart-text-muted)'; gearBtn.style.background = ''; });
                    gearBtn.addEventListener('click', function(e) {
                        e.stopPropagation();
                        _tvHideIndicatorsPanel();
                        _tvShowIndicatorSettings(sid);
                    });
                    item.appendChild(gearBtn);
                    var removeBtn = document.createElement('span');
                    removeBtn.textContent = '\u00d7';
                    removeBtn.style.cssText = 'cursor:pointer;font-size:18px;color:' + _cssVar('--pywry-draw-danger', '#f44336') + ';';
                    removeBtn.addEventListener('click', function(e) {
                        e.stopPropagation();
                        _tvRemoveIndicator(sid);
                        renderList(searchInp.value);
                    });
                    item.appendChild(removeBtn);
                    list.appendChild(item);
                })(activeKeys[a], ai);
            }
        }

        // Catalog
        var secNames = {};
        var filtered = _INDICATOR_CATALOG.filter(function(ind) {
            if (!filter) return true;
            return ind.fullName.toLowerCase().indexOf(filter.toLowerCase()) !== -1 ||
                   ind.name.toLowerCase().indexOf(filter.toLowerCase()) !== -1;
        });

        var currentCat = '';
        for (var ci = 0; ci < filtered.length; ci++) {
            var ind = filtered[ci];
            if (ind.category !== currentCat) {
                currentCat = ind.category;
                if (currentCat !== 'Lightweight Examples') {
                    var sec = document.createElement('div');
                    sec.className = 'tv-indicators-section';
                    sec.textContent = currentCat.toUpperCase();
                    list.appendChild(sec);
                }
            }
            (function(indDef) {
                var item = document.createElement('div');
                item.className = 'tv-indicator-item';
                var nameSpan = document.createElement('span');
                nameSpan.className = 'ind-name';
                nameSpan.textContent = indDef.fullName;
                item.appendChild(nameSpan);
                item.addEventListener('click', function() {
                    _tvAddIndicator(indDef, chartId);
                    renderList(searchInp.value);
                });
                list.appendChild(item);
            })(ind);
        }
    }

    searchInp.addEventListener('input', function() { renderList(searchInp.value); });
    renderList('');

    _tvAppendOverlay(chartId, overlay);
    searchInp.focus();
}

