function _tvSwapIndicatorPane(chartId, seriesId, direction) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.chart) return;
    var info = _activeIndicators[seriesId];
    if (!info || !info.isSubplot) return;

    // Restore panes to normal before swapping so heights are sane
    var pState = _tvGetPaneState(chartId);
    if (pState.mode !== 'normal') {
        _tvRestorePanes(chartId);
    }

    var targetPane = info.paneIndex + direction;
    if (targetPane < 0) return; // Can't move above the first pane

    // Count the total number of panes via LWC API
    var totalPanes = 0;
    try {
        if (typeof entry.chart.panes === 'function') {
            totalPanes = entry.chart.panes().length;
        }
    } catch (e) {}
    if (totalPanes <= 0) {
        // Fallback: count from tracked indicators + volume
        var allKeys = Object.keys(_activeIndicators);
        for (var i = 0; i < allKeys.length; i++) {
            var ai = _activeIndicators[allKeys[i]];
            if (ai && ai.chartId === chartId && ai.paneIndex > totalPanes) {
                totalPanes = ai.paneIndex;
            }
        }
        totalPanes += 1; // convert max index to count
    }
    if (targetPane >= totalPanes) return; // Can't move below last pane

    // Use LWC v5 swapPanes API
    try {
        if (typeof entry.chart.swapPanes === 'function') {
            entry.chart.swapPanes(info.paneIndex, targetPane);
        } else {
            return; // API not available
        }
    } catch (e) {
        return;
    }

    var oldPane = info.paneIndex;

    // Update paneIndex tracking for all affected indicators
    var allKeys2 = Object.keys(_activeIndicators);
    for (var j = 0; j < allKeys2.length; j++) {
        var aj = _activeIndicators[allKeys2[j]];
        if (!aj || aj.chartId !== chartId) continue;
        if (aj.paneIndex === oldPane) {
            aj.paneIndex = targetPane;
        } else if (aj.paneIndex === targetPane) {
            aj.paneIndex = oldPane;
        }
    }

    // Update volume pane tracking if swap involved a volume pane
    if (entry._volumePaneBySeries) {
        var volKeys = Object.keys(entry._volumePaneBySeries);
        for (var vi = 0; vi < volKeys.length; vi++) {
            var vk = volKeys[vi];
            if (entry._volumePaneBySeries[vk] === oldPane) {
                entry._volumePaneBySeries[vk] = targetPane;
            } else if (entry._volumePaneBySeries[vk] === targetPane) {
                entry._volumePaneBySeries[vk] = oldPane;
            }
        }
    }

    // Reposition the main chart legend to follow the pane it now lives in.
    // Deferred so the swap DOM changes are settled.
    requestAnimationFrame(function() {
        _tvRepositionMainLegend(entry, chartId);
    });

    _tvRebuildIndicatorLegend(chartId);
}

/**
 * Find which pane index the main chart series currently lives in.
 * Returns 0 if unknown.
 */
function _tvFindMainChartPane(entry) {
    if (!entry || !entry.chart) return 0;
    try {
        var panes = typeof entry.chart.panes === 'function' ? entry.chart.panes() : null;
        if (!panes) return 0;
        // The main chart series is the first entry in seriesMap
        var mainKey = Object.keys(entry.seriesMap)[0];
        var mainSeries = mainKey ? entry.seriesMap[mainKey] : null;
        if (!mainSeries) return 0;
        for (var pi = 0; pi < panes.length; pi++) {
            var pSeries = typeof panes[pi].getSeries === 'function' ? panes[pi].getSeries() : [];
            for (var si = 0; si < pSeries.length; si++) {
                if (pSeries[si] === mainSeries) return pi;
            }
        }
    } catch (e) {}
    return 0;
}

/**
 * Reposition the main legend box (OHLC, Volume text, indicators-in-main)
 * so it sits at the top of whichever pane the main chart series is in.
 * When the main chart is in pane 0 (default), top stays at 8px.
 * When it's been swapped to another pane, offset the legend accordingly.
 */
function _tvRepositionMainLegend(entry, chartId) {
    if (!entry || !entry.chart) return;
    var legendBox = _tvScopedById(chartId, 'tvchart-legend-box');
    if (!legendBox) return;

    var mainPane = _tvFindMainChartPane(entry);
    if (mainPane === 0) {
        // Default position
        legendBox.style.top = '8px';
        return;
    }

    try {
        var panes = typeof entry.chart.panes === 'function' ? entry.chart.panes() : null;
        if (!panes || !panes[mainPane]) { legendBox.style.top = '8px'; return; }
        var paneHtml = typeof panes[mainPane].getHTMLElement === 'function'
            ? panes[mainPane].getHTMLElement() : null;
        if (!paneHtml) { legendBox.style.top = '8px'; return; }
        // The legend box is positioned relative to the inside toolbar overlay
        // which matches the chart container bounds exactly.
        var containerRect = entry.container.getBoundingClientRect();
        var paneRect = paneHtml.getBoundingClientRect();
        var offset = paneRect.top - containerRect.top;
        legendBox.style.top = (offset + 8) + 'px';
    } catch (e) {
        legendBox.style.top = '8px';
    }
}

/**
 * Get the current state of a pane: 'normal', 'maximized', or 'collapsed'.
 */
function _tvGetPaneState(chartId) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry) return { mode: 'normal', pane: -1 };
    if (!entry._paneState) entry._paneState = { mode: 'normal', pane: -1 };
    return entry._paneState;
}

/**
 * Save the current pane heights before maximize/collapse so we can
 * restore them later.
 */
function _tvSavePaneHeights(entry) {
    if (!entry || !entry.chart) return;
    try {
        var panes = entry.chart.panes();
        if (!panes) return;
        entry._savedPaneHeights = [];
        for (var i = 0; i < panes.length; i++) {
            var el = typeof panes[i].getHTMLElement === 'function'
                ? panes[i].getHTMLElement() : null;
            entry._savedPaneHeights.push(el ? el.clientHeight : 0);
        }
    } catch (e) {}
}

/**
 * Hide or show LWC pane HTML elements and separator bars.
 * LWC renders panes as table-row elements inside a table; separators
 * are sibling rows.  We walk the parent and hide everything except the
 * target pane's row.
 */
function _tvSetPaneVisibility(panes, visibleIndex, hidden) {
    for (var k = 0; k < panes.length; k++) {
        var el = typeof panes[k].getHTMLElement === 'function'
            ? panes[k].getHTMLElement() : null;
        if (!el) continue;
        if (hidden && k !== visibleIndex) {
            el.style.display = 'none';
            // Also hide the separator bar above (previous sibling of the pane)
            var sep = el.previousElementSibling;
            if (sep && sep !== el.parentElement.firstElementChild) {
                sep.style.display = 'none';
            }
        } else {
            el.style.display = '';
            var sep2 = el.previousElementSibling;
            if (sep2 && sep2 !== el.parentElement.firstElementChild) {
                sep2.style.display = '';
            }
        }
    }
}

/**
 * Show or hide the legend boxes to match which panes are visible.
 *   mode='normal'    — show everything
 *   mode='maximized' — show only the legend for `pane`, hide others
 *   mode='collapsed' — hide the legend for `pane`, show others
 */
function _tvSyncLegendVisibility(chartId, mode, pane) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry) return;

    // Main legend box (OHLC, Volume, indicators-in-main-pane)
    var legendBox = _tvScopedById(chartId, 'tvchart-legend-box');
    var mainPane = _tvFindMainChartPane(entry);

    if (mode === 'normal') {
        // Show everything
        if (legendBox) legendBox.style.display = '';
        if (entry._paneLegendEls) {
            var pKeys = Object.keys(entry._paneLegendEls);
            for (var i = 0; i < pKeys.length; i++) {
                entry._paneLegendEls[pKeys[i]].style.display = '';
            }
        }
    } else if (mode === 'maximized') {
        // Hide main legend if main chart pane is not the maximized one
        if (legendBox) legendBox.style.display = (mainPane === pane) ? '' : 'none';
        // Hide all pane overlays except for the maximized pane
        if (entry._paneLegendEls) {
            var mKeys = Object.keys(entry._paneLegendEls);
            for (var m = 0; m < mKeys.length; m++) {
                var idx = Number(mKeys[m]);
                entry._paneLegendEls[mKeys[m]].style.display = (idx === pane) ? '' : 'none';
            }
        }
    } else if (mode === 'collapsed') {
        // Show all legends — the collapsed pane still shows its legend in the thin strip
        if (legendBox) legendBox.style.display = '';
        if (entry._paneLegendEls) {
            var cKeys = Object.keys(entry._paneLegendEls);
            for (var c = 0; c < cKeys.length; c++) {
                entry._paneLegendEls[cKeys[c]].style.display = '';
            }
        }
    }
}

/**
 * Maximize a pane: hide every other pane so it fills the entire chart area.
 */
function _tvMaximizePane(chartId, paneIndex) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.chart) return;
    try {
        if (typeof entry.chart.panes !== 'function') return;
        var panes = entry.chart.panes();
        if (!panes || !panes[paneIndex]) return;
        var state = _tvGetPaneState(chartId);

        // If already maximized on this pane, restore instead
        if (state.mode === 'maximized' && state.pane === paneIndex) {
            _tvRestorePanes(chartId);
            return;
        }

        // If currently in another mode, restore first
        if (state.mode !== 'normal') {
            _tvSetPaneVisibility(panes, -1, false); // unhide all
        }

        // Save heights only from normal state
        if (state.mode === 'normal') {
            _tvSavePaneHeights(entry);
        }

        // Hide every other pane + its surrounding separator bars so no
        // grey strips steal pixels.  Then use LWC's setStretchFactor
        // to give the target pane all the proportional space —
        // setStretchFactor lets LWC distribute container height
        // automatically, so we don't have to fight with pixel math
        // (which leaves dead space because LWC re-distributes to its
        // own minimums).  Stretch ratios: target = 10000, others = 0.001.
        _tvSetPaneVisibilityFull(panes, paneIndex);

        for (var __pi = 0; __pi < panes.length; __pi++) {
            var p = panes[__pi];
            if (!p) continue;
            // Save original stretch factor for restore (default 1).
            if (entry._savedStretchFactors == null) entry._savedStretchFactors = [];
            if (entry._savedStretchFactors[__pi] == null) {
                try {
                    entry._savedStretchFactors[__pi] = (typeof p.getStretchFactor === 'function')
                        ? p.getStretchFactor() : 1;
                } catch (_e0) { entry._savedStretchFactors[__pi] = 1; }
            }
            if (typeof p.setStretchFactor === 'function') {
                try { p.setStretchFactor(__pi === paneIndex ? 10000 : 0.001); } catch (_e) {}
            } else if (typeof p.setHeight === 'function') {
                // Fallback for older LWC
                try { p.setHeight(__pi === paneIndex ? 10000 : 1); } catch (_e2) {}
            }
        }

        // Force a chart redraw so LWC honours the new stretch factors.
        try {
            entry.chart.applyOptions({ autoSize: true });
            var w = entry.container ? entry.container.clientWidth : 800;
            var h = entry.container ? entry.container.clientHeight : 600;
            if (typeof entry.chart.resize === 'function') entry.chart.resize(w, h);
        } catch (_e3) {}

        requestAnimationFrame(function() {
            _tvRepositionPaneLegends(chartId);
        });

        entry._paneState = { mode: 'maximized', pane: paneIndex };
        _tvSyncLegendVisibility(chartId, 'maximized', paneIndex);
        _tvUpdatePaneControlButtons(chartId);
    } catch (e) {}
}

/**
 * Like _tvSetPaneVisibility but ALSO hides the separator BELOW each
 * non-target pane (the current helper only hides the one above).
 * Without this the thin grey separators stack up and steal real
 * pixels from the maximized pane.
 */
function _tvSetPaneVisibilityFull(panes, visibleIndex) {
    for (var k = 0; k < panes.length; k++) {
        var el = typeof panes[k].getHTMLElement === 'function' ? panes[k].getHTMLElement() : null;
        if (!el) continue;
        if (k !== visibleIndex) {
            el.style.display = 'none';
            var prevSep = el.previousElementSibling;
            if (prevSep && prevSep !== el.parentElement.firstElementChild) prevSep.style.display = 'none';
            var nextSep = el.nextElementSibling;
            if (nextSep && nextSep.tagName !== el.tagName) nextSep.style.display = 'none';
        } else {
            el.style.display = '';
        }
    }
}

/**
 * Collapse a pane: shrink it to a thin strip showing only the legend text.
 * The pane stays visible but its chart content is clipped.
 */
function _tvCollapsePane(chartId, paneIndex) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.chart) return;
    try {
        if (typeof entry.chart.panes !== 'function') return;
        var panes = entry.chart.panes();
        if (!panes || !panes[paneIndex]) return;
        var state = _tvGetPaneState(chartId);

        // If already collapsed on this pane, restore instead
        if (state.mode === 'collapsed' && state.pane === paneIndex) {
            _tvRestorePanes(chartId);
            return;
        }

        // If currently in another mode, restore first
        if (state.mode !== 'normal') {
            _tvSetPaneVisibility(panes, -1, false);
            _tvShowPaneContent(panes, -1); // unhide any hidden canvases
        }

        // Save heights only from normal state
        if (state.mode === 'normal') {
            _tvSavePaneHeights(entry);
        }

        // Shrink pane to minimal via LWC API, then hide all canvas/content
        // children so only the empty strip remains for the legend overlay.
        if (typeof panes[paneIndex].setHeight === 'function') {
            panes[paneIndex].setHeight(1);
        }
        _tvHidePaneContent(panes[paneIndex]);

        entry._paneState = { mode: 'collapsed', pane: paneIndex };
        _tvSyncLegendVisibility(chartId, 'collapsed', paneIndex);
        _tvUpdatePaneControlButtons(chartId);
        requestAnimationFrame(function() {
            _tvRepositionPaneLegends(chartId);
        });
    } catch (e) {}
}

/**
 * Hide all visual content (canvases, child elements) inside a pane,
 * leaving the pane element itself visible at whatever height LWC gives it.
 */
function _tvHidePaneContent(pane) {
    var el = typeof pane.getHTMLElement === 'function' ? pane.getHTMLElement() : null;
    if (!el) return;
    // Hide every child element inside the pane (canvas, scale elements, etc.)
    var children = el.querySelectorAll('*');
    for (var i = 0; i < children.length; i++) {
        children[i].style.visibility = 'hidden';
    }
}

/**
 * Restore visibility to pane content.
 * If paneIndex is -1, restores all panes.
 */
function _tvShowPaneContent(panes, paneIndex) {
    for (var k = 0; k < panes.length; k++) {
        if (paneIndex >= 0 && k !== paneIndex) continue;
        var el = typeof panes[k].getHTMLElement === 'function'
            ? panes[k].getHTMLElement() : null;
        if (!el) continue;
        var children = el.querySelectorAll('*');
        for (var j = 0; j < children.length; j++) {
            children[j].style.visibility = '';
        }
    }
}

/**
 * Restore all panes to their saved heights (before maximize/collapse).
 */
function _tvRestorePanes(chartId) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.chart) return;
    try {
        if (typeof entry.chart.panes !== 'function') return;
        var panes = entry.chart.panes();
        if (!panes) return;

        // Unhide all panes (from maximize) and restore content (from collapse)
        _tvSetPaneVisibility(panes, -1, false);
        _tvShowPaneContent(panes, -1);

        // Restore stretch factors from maximize (so panes go back to their
        // original proportional space).  Falls back to setHeight if
        // setStretchFactor isn't available.
        if (entry._savedStretchFactors && entry._savedStretchFactors.length === panes.length) {
            for (var __sr = 0; __sr < panes.length; __sr++) {
                var __pp = panes[__sr];
                if (__pp && typeof __pp.setStretchFactor === 'function') {
                    try { __pp.setStretchFactor(entry._savedStretchFactors[__sr] || 1); } catch (_e) {}
                }
            }
        }
        delete entry._savedStretchFactors;

        var saved = entry._savedPaneHeights;
        if (saved && saved.length === panes.length) {
            for (var i = 0; i < panes.length; i++) {
                if (typeof panes[i].setHeight === 'function' && saved[i] > 0) {
                    panes[i].setHeight(saved[i]);
                }
            }
        } else {
            // Fallback: equal distribution
            var containerH = entry.container ? entry.container.clientHeight : 600;
            for (var j = 0; j < panes.length; j++) {
                if (typeof panes[j].setHeight === 'function') {
                    panes[j].setHeight(Math.round(containerH / panes.length));
                }
            }
        }
        entry._paneState = { mode: 'normal', pane: -1 };
        delete entry._savedPaneHeights;
        _tvSyncLegendVisibility(chartId, 'normal', -1);
        _tvUpdatePaneControlButtons(chartId);
        requestAnimationFrame(function() {
            _tvRepositionPaneLegends(chartId);
        });
    } catch (e) {}
}

/**
 * Update the maximize/collapse/restore button icon and tooltip for every
 * subplot indicator in the given chart, reflecting the current pane state.
 */
function _tvUpdatePaneControlButtons(chartId) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry) return;
    var state = _tvGetPaneState(chartId);
    var restoreSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="display:block"><rect x="1.5" y="4.5" width="9" height="9" rx="1.5"/><path d="M5.5 4.5V3a1.5 1.5 0 011.5-1.5h6A1.5 1.5 0 0114.5 3v6a1.5 1.5 0 01-1.5 1.5h-1.5"/></svg>';
    var maximizeSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="display:block"><rect x="2.5" y="2.5" width="11" height="11" rx="1.5"/></svg>';
    var collapseSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="display:block"><line x1="3" y1="8" x2="13" y2="8"/></svg>';

    var keys = Object.keys(_activeIndicators);
    for (var i = 0; i < keys.length; i++) {
        var info = _activeIndicators[keys[i]];
        if (!info || info.chartId !== chartId || !info.isSubplot) continue;
        var isThisPane = state.pane === info.paneIndex;

        // Update maximize button
        var btn = document.getElementById('tvchart-pane-ctrl-' + keys[i]);
        if (btn) {
            if (state.mode === 'maximized' && isThisPane) {
                btn.innerHTML = restoreSvg;
                btn.setAttribute('data-tooltip', 'Restore pane');
                btn.setAttribute('aria-label', 'Restore pane');
            } else {
                btn.innerHTML = maximizeSvg;
                btn.setAttribute('data-tooltip', 'Maximize pane');
                btn.setAttribute('aria-label', 'Maximize pane');
            }
        }

        // Update collapse button
        var cBtn = document.getElementById('tvchart-pane-collapse-' + keys[i]);
        if (cBtn) {
            if (state.mode === 'collapsed' && isThisPane) {
                cBtn.innerHTML = restoreSvg;
                cBtn.setAttribute('data-tooltip', 'Restore pane');
                cBtn.setAttribute('aria-label', 'Restore pane');
            } else {
                cBtn.innerHTML = collapseSvg;
                cBtn.setAttribute('data-tooltip', 'Collapse pane');
                cBtn.setAttribute('aria-label', 'Collapse pane');
            }
        }
    }
}

/**
 * Get or create a legend overlay for a specific pane, positioned absolutely
 * inside entry.container (the chart wrapper div).
 */
function _tvGetPaneLegendContainer(entry, paneIndex) {
    if (!entry._paneLegendEls) entry._paneLegendEls = {};
    if (entry._paneLegendEls[paneIndex]) return entry._paneLegendEls[paneIndex];

    var container = entry.container;
    if (!container || !entry.chart) return null;

    try {
        if (typeof entry.chart.panes !== 'function') return null;
        var panes = entry.chart.panes();
        if (!panes || !panes[paneIndex]) return null;

        // Compute the top offset and height of this pane relative to the container
        var top = 0;
        var paneHeight = 0;
        var paneHtml = typeof panes[paneIndex].getHTMLElement === 'function'
            ? panes[paneIndex].getHTMLElement() : null;
        if (paneHtml) {
            var paneRect = paneHtml.getBoundingClientRect();
            var containerRect = container.getBoundingClientRect();
            top = paneRect.top - containerRect.top;
            paneHeight = paneRect.height;
        } else {
            // Fallback: sum preceding pane heights + 1px separators
            for (var i = 0; i < paneIndex; i++) {
                var ps = typeof entry.chart.paneSize === 'function'
                    ? entry.chart.paneSize(i) : null;
                top += (ps ? ps.height : 0) + 1;
            }
            var curPs = typeof entry.chart.paneSize === 'function'
                ? entry.chart.paneSize(paneIndex) : null;
            paneHeight = curPs ? curPs.height : 0;
        }

        var overlay = document.createElement('div');
        overlay.className = 'tvchart-pane-legend';
        overlay.style.top = (top + 4) + 'px';
        if (paneHeight > 0) {
            overlay.style.maxHeight = (paneHeight - 8) + 'px';
            overlay.style.overflow = 'hidden';
        }
        container.appendChild(overlay);
        entry._paneLegendEls[paneIndex] = overlay;
        return overlay;
    } catch (e) {
        return null;
    }
}

/**
 * Reposition existing per-pane legend overlays (e.g. after pane resize via divider drag).
 */
function _tvRepositionPaneLegends(chartId) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry._paneLegendEls || !entry.chart || !entry.container) return;
    var container = entry.container;
    var panes;
    try { panes = typeof entry.chart.panes === 'function' ? entry.chart.panes() : null; } catch (e) { return; }
    if (!panes) return;

    for (var pi in entry._paneLegendEls) {
        var overlay = entry._paneLegendEls[pi];
        if (!overlay) continue;
        var idx = Number(pi);
        var paneHtml = panes[idx] && typeof panes[idx].getHTMLElement === 'function'
            ? panes[idx].getHTMLElement() : null;
        if (paneHtml) {
            var paneRect = paneHtml.getBoundingClientRect();
            var containerRect = container.getBoundingClientRect();
            overlay.style.top = (paneRect.top - containerRect.top + 4) + 'px';
            if (paneRect.height > 0) {
                overlay.style.maxHeight = (paneRect.height - 8) + 'px';
            }
        }
    }

    // Also keep the main legend box tracking its pane (after swaps)
    _tvRepositionMainLegend(entry, chartId);
}

