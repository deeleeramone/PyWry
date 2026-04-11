// ==========================================================================
// 11-legend.js  –  Legend controls & crosshair-move legend updater
// ==========================================================================

/**
 * Set up legend controls (eye/settings/remove buttons, context menus,
 * compare-series rows, crosshair-move legend updater) for a chart.
 * Called once per chart from the lifecycle create path.
 *
 * @param {string} chartId
 */
function _tvSetupLegendControls(chartId) {
    var resolved = _tvResolveChartEntry(chartId);
    if (!resolved || !resolved.entry) return;
    var entry = resolved.entry;
    if (!entry.chart) return;

    function scopedById(id) {
        return _tvScopedById(chartId, id);
    }

    function resolveLegendNodes() {
        return {
            titleEl: scopedById('tvchart-legend-title'),
            ohlcEl: scopedById('tvchart-legend-ohlc'),
            seriesEl: scopedById('tvchart-legend-series'),
            volEl: scopedById('tvchart-legend-vol'),
            mainRowEl: scopedById('tvchart-legend-main-row'),
            volRowEl: scopedById('tvchart-legend-vol-row'),
            mainCtrlEl: scopedById('tvchart-legend-main-ctrl'),
            volCtrlEl: scopedById('tvchart-legend-vol-ctrl'),
            boxEl: scopedById('tvchart-legend-box'),
        };
    }

    function fmt(v) {
        if (v == null) return '--';
        return Number(v).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
    }
    function fmtVol(v) {
        if (v == null) return '';
        if (v >= 1e9) return (v / 1e9).toFixed(2) + ' B';
        if (v >= 1e6) return (v / 1e6).toFixed(2) + ' M';
        if (v >= 1e3) return (v / 1e3).toFixed(2) + ' K';
        return v.toFixed(0);
    }

    var _dimColor = 'var(--pywry-tvchart-text-dim)';
    var _upColor = 'var(--pywry-tvchart-up)';
    var _downColor = 'var(--pywry-tvchart-down)';
    var _mutedColor = 'var(--pywry-tvchart-text-muted)';
    var _activeColor = 'var(--pywry-tvchart-active-text)';
    var _sessionBreaksColor = 'var(--pywry-tvchart-session-breaks)';
    var _borderStrongColor = 'var(--pywry-tvchart-border-strong)';

    function colorize(val, ref) {
        if (val == null || ref == null) return _mutedColor;
        return val >= ref ? _upColor : _downColor;
    }


    function _legendNormalizeTimeValue(value) {
        if (value == null) return null;
        if (typeof value === 'number') return value;
        if (typeof value === 'string') {
            var parsed = Date.parse(value);
            return isFinite(parsed) ? Math.floor(parsed / 1000) : value;
        }
        if (typeof value === 'object') {
            if (typeof value.timestamp === 'number') return value.timestamp;
            if (typeof value.year === 'number' && typeof value.month === 'number' && typeof value.day === 'number') {
                return Date.UTC(value.year, value.month - 1, value.day) / 1000;
            }
        }
        return null;
    }

    function _legendResolveHoveredPoint(seriesId, sApi, param) {
        var direct = (param && param.seriesData && sApi) ? param.seriesData.get(sApi) : null;
        if (direct) return direct;

        var rows = entry && entry._seriesRawData ? entry._seriesRawData[seriesId] : null;
        if (!rows || !rows.length || !param || param.time == null) return null;

        var target = _legendNormalizeTimeValue(param.time);
        if (target == null) return null;

        var best = null;
        var bestTime = null;
        for (var idx = 0; idx < rows.length; idx++) {
            var row = rows[idx];
            var rowTime = _legendNormalizeTimeValue(row && row.time);
            if (rowTime == null) continue;
            if (rowTime === target) return row;
            if (rowTime <= target) {
                best = row;
                bestTime = rowTime;
                continue;
            }
            if (bestTime == null) return row;
            return best;
        }
        return best;
    }


    var legendNodes = resolveLegendNodes();
    var titleEl = legendNodes.titleEl;
    var ohlcEl = legendNodes.ohlcEl;
    var seriesEl = legendNodes.seriesEl;
    var volEl = legendNodes.volEl;
    var mainRowEl = legendNodes.mainRowEl;
    var volRowEl = legendNodes.volRowEl;
    var mainCtrlEl = legendNodes.mainCtrlEl;
    var volCtrlEl = legendNodes.volCtrlEl;
    if (!titleEl || !ohlcEl) return;


    var initialSeriesKeys = Object.keys(entry.seriesMap || {});
    var mainKey = (initialSeriesKeys.indexOf('main') >= 0) ? 'main' : (initialSeriesKeys[0] || chartId);
    var hideSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" style="display:block"><path d="M1.8 8s2.2-3.8 6.2-3.8S14.2 8 14.2 8s-2.2 3.8-6.2 3.8S1.8 8 1.8 8z"/><circle cx="8" cy="8" r="1.9"/></svg>';
    var showSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" style="display:block"><path d="M1.8 8s2.2-3.8 6.2-3.8S14.2 8 14.2 8s-2.2 3.8-6.2 3.8S1.8 8 1.8 8z"/><circle cx="8" cy="8" r="1.9"/><line x1="3" y1="13" x2="13" y2="3" stroke-width="1.6"/></svg>';
    var settingsSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor" style="display:block"><path d="M8 10.2a2.2 2.2 0 100-4.4 2.2 2.2 0 000 4.4zm4.8-2.7a.5.5 0 01.3-.46l.46-.27a.5.5 0 00.18-.68l-.54-.94a.5.5 0 00-.68-.18l-.46.27a.5.5 0 01-.53-.05 4.4 4.4 0 00-.55-.32.5.5 0 01-.3-.45V3.9A.5.5 0 0010.19 3.5H9.12a.5.5 0 00-.5.46v.51a.5.5 0 01-.3.45 4.4 4.4 0 00-.55.32.5.5 0 01-.53.05l-.46-.27a.5.5 0 00-.68.18l-.54.94a.5.5 0 00.18.68l.46.27a.5.5 0 01.3.46v.02a.5.5 0 01-.3.46l-.46.27a.5.5 0 00-.18.68l.54.94a.5.5 0 00.68.18l.46-.27a.5.5 0 01.53.05c.17.12.35.22.55.32a.5.5 0 01.3.45v.51A.5.5 0 0010.19 12.5H9.12a.5.5 0 01-.5-.46v-.51a.5.5 0 00-.3-.45 4.4 4.4 0 01-.55-.32.5.5 0 00-.53.05l-.46.27a.5.5 0 01-.68-.18l-.54-.94a.5.5 0 01.18-.68l.46-.27a.5.5 0 00.3-.46v-.02z"/></svg>';
    var removeSvg = '<svg viewBox="0 0 16 16" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" style="display:block"><line x1="4" y1="4" x2="12" y2="12"/><line x1="12" y1="4" x2="4" y2="12"/></svg>';
    var menuSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor" style="display:block"><circle cx="3.5" cy="8" r="1.2"/><circle cx="8" cy="8" r="1.2"/><circle cx="12.5" cy="8" r="1.2"/></svg>';
    var valuesSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" style="display:block"><polyline points="2,11 5.2,7.8 7.7,9.9 12.8,4.8"/><circle cx="12.8" cy="4.8" r="1" fill="currentColor" stroke="none"/></svg>';
    var copySvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" style="display:block"><rect x="5.2" y="3.6" width="7.2" height="8.6" rx="1.4"/><path d="M3.6 10.4V5.1c0-.9.7-1.6 1.6-1.6h4.4"/></svg>';
    var infoSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" style="display:block"><circle cx="8" cy="8" r="6.3"/><line x1="8" y1="7" x2="8" y2="11"/><circle cx="8" cy="4.8" r="0.8" fill="currentColor" stroke="none"/></svg>';
    var layersSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round" style="display:block"><path d="M2 6.3L8 3l6 3.3L8 9.7 2 6.3z"/><path d="M2.8 9.5L8 12.3l5.2-2.8"/></svg>';
    var intervalSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" style="display:block"><rect x="2.2" y="3" width="11.6" height="10" rx="1.8"/><line x1="2.2" y1="6.2" x2="13.8" y2="6.2"/><line x1="5.1" y1="1.8" x2="5.1" y2="4.4"/><line x1="10.9" y1="1.8" x2="10.9" y2="4.4"/></svg>';
    var moveSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" style="display:block"><path d="M8 1.8v12.4M1.8 8h12.4"/><path d="M8 1.8l1.8 1.8M8 1.8L6.2 3.6M8 14.2l1.8-1.8M8 14.2l-1.8-1.8M14.2 8l-1.8 1.8M14.2 8l-1.8-1.8M1.8 8l1.8 1.8M1.8 8l1.8-1.8"/></svg>';
    var pinSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" style="display:block"><path d="M5 3.5h6l-1.2 2.4v2.8l1.6 1.2H4.6l1.6-1.2V5.9L5 3.5z"/><path d="M8 10v4"/></svg>';
    var treeSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" style="display:block"><rect x="2" y="2.5" width="4" height="3" rx="0.8"/><rect x="10" y="2.5" width="4" height="3" rx="0.8"/><rect x="6" y="10.5" width="4" height="3" rx="0.8"/><path d="M4 5.5v2h8v-2M8 7.5v3"/></svg>';
    var legendUiState = entry._legendUiState || { mainHidden: false, volumeHidden: false, seriesHidden: {}, indicatorsCollapsed: false };
    if (!legendUiState.seriesHidden) legendUiState.seriesHidden = {};
    entry._legendUiState = legendUiState;
    var legendMenuEl = null;
    var legendSecurityInfoOverlayEl = null;
    var legendObjectTreeOverlayEl = null;

    function _legendCloseMenu() {
        if (legendMenuEl && legendMenuEl.parentNode) {
            legendMenuEl.parentNode.removeChild(legendMenuEl);
        }
        legendMenuEl = null;
    }

    function _legendOpenMenu(anchorEl, actions) {
        _legendCloseMenu();
        if (!anchorEl || !actions || !actions.length) return;
        var menu = document.createElement('div');
        menu.className = 'tvchart-legend-menu';
        for (var mi = 0; mi < actions.length; mi++) {
            (function(action) {
                if (action.separator) {
                    var sep = document.createElement('div');
                    sep.className = 'tvchart-legend-menu-sep';
                    menu.appendChild(sep);
                    return;
                }
                var item = document.createElement('button');
                item.type = 'button';
                item.className = 'tvchart-legend-menu-item';
                if (action.disabled) {
                    item.disabled = true;
                    item.classList.add('is-disabled');
                }
                if (action.tooltip) {
                    item.setAttribute('data-tooltip', action.tooltip);
                }
                var icon = document.createElement('span');
                icon.className = 'tvchart-legend-menu-item-icon';
                icon.innerHTML = action.icon || '';
                item.appendChild(icon);
                var label = document.createElement('span');
                label.className = 'tvchart-legend-menu-item-label';
                label.textContent = action.label;
                item.appendChild(label);
                if (action.meta) {
                    var meta = document.createElement('span');
                    meta.className = 'tvchart-legend-menu-item-meta';
                    meta.textContent = action.meta;
                    item.appendChild(meta);
                }
                item.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    if (action.disabled) return;
                    _legendCloseMenu();
                    action.run();
                });
                menu.appendChild(item);
            })(actions[mi]);
        }
        menu.addEventListener('click', function(e) { e.stopPropagation(); });
        document.body.appendChild(menu);
        var rect = anchorEl.getBoundingClientRect();
        var menuRect = menu.getBoundingClientRect();
        var left = Math.max(6, Math.min(window.innerWidth - menuRect.width - 6, rect.right - menuRect.width));
        var top = Math.max(6, Math.min(window.innerHeight - menuRect.height - 6, rect.bottom + 4));
        menu.style.left = left + 'px';
        menu.style.top = top + 'px';
        legendMenuEl = menu;
        setTimeout(function() {
            document.addEventListener('click', _legendCloseMenu, { once: true });
        }, 0);
    }

    function _legendMakeButton(label, iconHtml, onClick) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'tvchart-legend-btn';
        btn.setAttribute('data-tooltip', label);
        btn.setAttribute('aria-label', label);
        btn.innerHTML = iconHtml;
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            onClick(btn);
        });
        return btn;
    }

    function _legendMainSeries() {
        var activeMainKey = 'main';
        var keys = Object.keys(entry.seriesMap || {});
        if (keys.indexOf('main') < 0) {
            activeMainKey = keys[0] || mainKey;
        }
        return entry.seriesMap[activeMainKey] || null;
    }

    function _legendApplyMainHidden(hidden) {
        legendUiState.mainHidden = !!hidden;
        var s = _legendMainSeries();
        if (s && typeof s.applyOptions === 'function') {
            try { s.applyOptions({ visible: !legendUiState.mainHidden }); } catch (e) {}
        }
        if (mainRowEl) mainRowEl.dataset.hidden = legendUiState.mainHidden ? '1' : '0';
    }

    function _legendApplyVolumeHidden(hidden) {
        legendUiState.volumeHidden = !!hidden;
        var volSeries = entry.volumeMap && entry.volumeMap.main ? entry.volumeMap.main : entry.seriesMap['volume'];
        if (volSeries && typeof volSeries.applyOptions === 'function') {
            try { volSeries.applyOptions({ visible: !legendUiState.volumeHidden }); } catch (e) {}
        }
        if (volRowEl) volRowEl.dataset.hidden = legendUiState.volumeHidden ? '1' : '0';
    }

    function _legendApplySeriesHidden(seriesId, hidden) {
        var sid = String(seriesId || '');
        if (!sid) return;
        if (!legendUiState.seriesHidden) legendUiState.seriesHidden = {};
        legendUiState.seriesHidden[sid] = !!hidden;
        if (!entry._seriesVisibilityOverrides) entry._seriesVisibilityOverrides = {};
        entry._seriesVisibilityOverrides[sid] = !legendUiState.seriesHidden[sid];
        var s = entry.seriesMap ? entry.seriesMap[sid] : null;
        if (s && typeof s.applyOptions === 'function') {
            try { s.applyOptions({ visible: !legendUiState.seriesHidden[sid] }); } catch (e) {}
        }
    }

    function _legendNormalizeSeriesOrder() {
        if (!entry) return;
        var keys = Object.keys(entry.seriesMap || {});
        var currentMainKey = (keys.indexOf('main') >= 0) ? 'main' : (keys[0] || mainKey);
        var allowed = [];
        for (var i = 0; i < keys.length; i++) {
            var sid = String(keys[i] || '');
            if (!sid || sid === currentMainKey || sid === 'volume' || sid.indexOf('ind_') === 0) continue;
            allowed.push(sid);
        }
        if (!entry._legendSeriesOrder || !Array.isArray(entry._legendSeriesOrder)) {
            entry._legendSeriesOrder = allowed.slice();
            return;
        }
        var filtered = [];
        for (var j = 0; j < entry._legendSeriesOrder.length; j++) {
            var existing = String(entry._legendSeriesOrder[j] || '');
            if (allowed.indexOf(existing) >= 0 && filtered.indexOf(existing) < 0) filtered.push(existing);
        }
        for (var k = 0; k < allowed.length; k++) {
            if (filtered.indexOf(allowed[k]) < 0) filtered.push(allowed[k]);
        }
        entry._legendSeriesOrder = filtered;
    }

    function _legendMoveSeriesOrder(seriesId, moveType) {
        _legendNormalizeSeriesOrder();
        var sid = String(seriesId || '');
        var order = entry._legendSeriesOrder || [];
        var idx = order.indexOf(sid);
        if (idx < 0) return;
        var nextIdx = idx;
        if (moveType === 'up') nextIdx = Math.max(0, idx - 1);
        else if (moveType === 'down') nextIdx = Math.min(order.length - 1, idx + 1);
        else if (moveType === 'top') nextIdx = 0;
        else if (moveType === 'bottom') nextIdx = order.length - 1;
        if (nextIdx === idx) return;
        order.splice(idx, 1);
        order.splice(nextIdx, 0, sid);
        entry._legendSeriesOrder = order;
    }

    function _legendSetSeriesScale(seriesId, scaleMode) {
        var sid = String(seriesId || '');
        if (!sid || !entry || !entry.seriesMap || !entry.seriesMap[sid]) return;
        if (!entry._seriesScaleModes) entry._seriesScaleModes = {};
        entry._seriesScaleModes[sid] = scaleMode;
        var series = entry.seriesMap[sid];
        var nextPriceScaleId = sid;
        if (scaleMode === 'left') nextPriceScaleId = 'left';
        else if (scaleMode === 'right') nextPriceScaleId = 'right';
        else if (scaleMode === 'none') nextPriceScaleId = 'overlay';
        try { series.applyOptions({ priceScaleId: nextPriceScaleId }); } catch (e) {}
    }

    function _legendGetSeriesScale(seriesId) {
        var sid = String(seriesId || '');
        if (!sid) return 'right';
        if (entry && entry._seriesScaleModes && entry._seriesScaleModes[sid]) return entry._seriesScaleModes[sid];
        var s = entry && entry.seriesMap ? entry.seriesMap[sid] : null;
        if (!s) return 'right';
        try {
            var opts = s.options ? s.options() : null;
            var ps = opts && opts.priceScaleId ? String(opts.priceScaleId) : sid;
            if (ps === 'left') return 'left';
            if (ps === 'overlay' || ps === 'none') return 'none';
        } catch (e) {}
        return 'right';
    }

    function _legendIntervalUnitKey(intervalText) {
        var raw = String(intervalText || '').trim().toLowerCase();
        if (!raw) return null;
        if (/s(ec(ond)?s?)?$/.test(raw)) return 'seconds';
        if (/m(in(ute)?s?)?$/.test(raw)) return 'minutes';
        if (/h(our)?s?$/.test(raw)) return 'hours';
        if (/d(ay)?s?$/.test(raw)) return 'days';
        if (/w(eek)?s?$/.test(raw)) return 'weeks';
        if (/mo(nth)?s?$/.test(raw) || /mth/.test(raw)) return 'months';
        if (/^[0-9]+$/.test(raw)) return 'minutes';
        return null;
    }

    function _legendIntervalValue(intervalText) {
        var raw = String(intervalText || '').trim().toLowerCase();
        if (!raw) return 1;
        var n = parseInt(raw, 10);
        if (isFinite(n) && n > 0) return n;
        var numMatch = raw.match(/^(\d+)/);
        if (numMatch) {
            var m = parseInt(numMatch[1], 10);
            if (isFinite(m) && m > 0) return m;
        }
        return 1;
    }

    function _legendGetIntervalText() {
        var ds = _legendDataset() || {};
        if (ds.interval) return String(ds.interval);
        if (entry && entry._activeInterval) return String(entry._activeInterval);
        if (entry && entry.payload && entry.payload.interval) return String(entry.payload.interval);
        return '1m';
    }

    function _legendEnsureVisibilityIntervals(seriesId) {
        var sid = String(seriesId || '');
        if (!sid) return null;
        if (!entry._seriesVisibilityIntervals) entry._seriesVisibilityIntervals = {};
        if (!entry._seriesVisibilityIntervals[sid]) {
            entry._seriesVisibilityIntervals[sid] = {
                seconds: { enabled: true, min: 1, max: 59 },
                minutes: { enabled: true, min: 1, max: 59 },
                hours: { enabled: true, min: 1, max: 24 },
                days: { enabled: true, min: 1, max: 366 },
                weeks: { enabled: true, min: 1, max: 52 },
                months: { enabled: true, min: 1, max: 12 },
            };
        }
        return entry._seriesVisibilityIntervals[sid];
    }

    function _legendIsSeriesVisibleForCurrentInterval(seriesId) {
        var sid = String(seriesId || '');
        if (!sid) return true;
        var cfg = _legendEnsureVisibilityIntervals(sid);
        if (!cfg) return true;
        var unit = _legendIntervalUnitKey(_legendGetIntervalText());
        var value = _legendIntervalValue(_legendGetIntervalText());
        if (!unit || !cfg[unit]) return true;
        var row = cfg[unit] || {};
        if (row.enabled === false) return false;
        var min = Number(row.min || 1);
        var max = Number(row.max || min);
        if (!isFinite(min)) min = 1;
        if (!isFinite(max)) max = min;
        if (min > max) {
            var t = min; min = max; max = t;
        }
        return value >= min && value <= max;
    }

    function _legendApplySeriesIntervalVisibility(seriesId) {
        var sid = String(seriesId || '');
        if (!sid) return;
        var hiddenByUser = !!(legendUiState.seriesHidden && legendUiState.seriesHidden[sid]);
        var visibleByInterval = _legendIsSeriesVisibleForCurrentInterval(sid);
        var visible = !hiddenByUser && visibleByInterval;
        if (!entry._seriesVisibilityOverrides) entry._seriesVisibilityOverrides = {};
        entry._seriesVisibilityOverrides[sid] = visible;
        var s = entry.seriesMap ? entry.seriesMap[sid] : null;
        if (s && typeof s.applyOptions === 'function') {
            try { s.applyOptions({ visible: visible }); } catch (e) {}
        }
    }

    function _legendApplyAllSeriesIntervalVisibility() {
        var keys = Object.keys((entry && entry.seriesMap) || {});
        for (var i = 0; i < keys.length; i++) {
            var sid = String(keys[i] || '');
            if (!sid || sid === 'main' || sid === 'volume' || sid.indexOf('ind_') === 0) continue;
            _legendApplySeriesIntervalVisibility(sid);
        }
    }

    function _legendOpenVisibilityIntervalsDialog(seriesId, rerenderFn) {
        var sid = String(seriesId || '');
        if (!sid) return;
        _legendCloseSecurityInfo();
        _legendCloseObjectTree();

        var cfg = _legendEnsureVisibilityIntervals(sid);
        if (!cfg) return;

        var overlay = document.createElement('div');
        overlay.className = 'tv-settings-overlay';
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) closeOverlay();
        });
        overlay.addEventListener('mousedown', function(e) { e.stopPropagation(); });
        overlay.addEventListener('wheel', function(e) { e.stopPropagation(); });

        var panel = document.createElement('div');
        panel.className = 'tv-settings-panel';
        panel.style.cssText = 'width:680px;max-width:calc(100% - 40px);max-height:78vh;display:flex;flex-direction:column;';

        function closeOverlay() {
            if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
        }

        var header = document.createElement('div');
        header.className = 'tv-settings-header';
        header.style.cssText = 'position:relative;display:flex;align-items:center;gap:8px;';
        var title = document.createElement('h3');
        title.textContent = _legendSeriesLabel(sid) + ' - Visibility on intervals';
        header.appendChild(title);
        var closeBtn = document.createElement('button');
        closeBtn.className = 'tv-settings-close';
        closeBtn.innerHTML = '<svg viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>';
        closeBtn.addEventListener('click', closeOverlay);
        header.appendChild(closeBtn);
        panel.appendChild(header);

        var body = document.createElement('div');
        body.className = 'tv-settings-body';
        body.style.cssText = 'flex:1;overflow-y:auto;';

        var defs = [
            { key: 'seconds', label: 'Seconds', max: 59 },
            { key: 'minutes', label: 'Minutes', max: 59 },
            { key: 'hours', label: 'Hours', max: 24 },
            { key: 'days', label: 'Days', max: 366 },
            { key: 'weeks', label: 'Weeks', max: 52 },
            { key: 'months', label: 'Months', max: 12 },
        ];

        for (var di = 0; di < defs.length; di++) {
            (function(def) {
                if (!cfg[def.key]) cfg[def.key] = { enabled: true, min: 1, max: def.max };
                var rowCfg = cfg[def.key];
                var row = document.createElement('div');
                row.className = 'tv-settings-row tv-settings-row-spaced';
                row.style.alignItems = 'center';

                var left = document.createElement('div');
                left.style.cssText = 'display:flex;align-items:center;gap:10px;min-width:130px;';
                var cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.className = 'ts-checkbox';
                cb.checked = rowCfg.enabled !== false;
                cb.addEventListener('change', function() { rowCfg.enabled = !!cb.checked; });
                left.appendChild(cb);
                var lbl = document.createElement('span');
                lbl.textContent = def.label;
                left.appendChild(lbl);
                row.appendChild(left);

                var minInput = document.createElement('input');
                minInput.type = 'number';
                minInput.className = 'ts-input';
                minInput.min = '1';
                minInput.max = String(def.max);
                minInput.style.width = '74px';
                minInput.value = String(Math.max(1, Math.min(def.max, Number(rowCfg.min || 1))));
                minInput.addEventListener('input', function() { rowCfg.min = Number(minInput.value || 1); });
                row.appendChild(minInput);

                var rail = document.createElement('div');
                rail.style.cssText = 'position:relative;flex:1;min-width:120px;max-width:180px;height:14px;';
                rail.innerHTML = '<div style="position:absolute;left:0;right:0;top:6px;height:3px;border-radius:3px;background:var(--pywry-tvchart-border-strong);"></div>';
                var k1 = document.createElement('span');
                k1.style.cssText = 'position:absolute;left:0;top:1px;width:12px;height:12px;border-radius:50%;background:var(--pywry-tvchart-panel-bg);border:2px solid var(--pywry-tvchart-border-strong);box-sizing:border-box;';
                var k2 = document.createElement('span');
                k2.style.cssText = 'position:absolute;right:0;top:1px;width:12px;height:12px;border-radius:50%;background:var(--pywry-tvchart-panel-bg);border:2px solid var(--pywry-tvchart-border-strong);box-sizing:border-box;';
                rail.appendChild(k1);
                rail.appendChild(k2);
                row.appendChild(rail);

                var maxInput = document.createElement('input');
                maxInput.type = 'number';
                maxInput.className = 'ts-input';
                maxInput.min = '1';
                maxInput.max = String(def.max);
                maxInput.style.width = '74px';
                maxInput.value = String(Math.max(1, Math.min(def.max, Number(rowCfg.max || def.max))));
                maxInput.addEventListener('input', function() { rowCfg.max = Number(maxInput.value || def.max); });
                row.appendChild(maxInput);
                body.appendChild(row);
            })(defs[di]);
        }

        panel.appendChild(body);

        var footer = document.createElement('div');
        footer.className = 'tv-settings-footer';
        footer.style.position = 'relative';
        var cancel = document.createElement('button');
        cancel.className = 'ts-btn-cancel';
        cancel.textContent = 'Cancel';
        cancel.addEventListener('click', closeOverlay);
        footer.appendChild(cancel);
        var ok = document.createElement('button');
        ok.className = 'ts-btn-ok';
        ok.textContent = 'Ok';
        ok.addEventListener('click', function() {
            if (!entry._seriesVisibilityIntervals) entry._seriesVisibilityIntervals = {};
            entry._seriesVisibilityIntervals[sid] = cfg;
            _legendApplySeriesIntervalVisibility(sid);
            if (typeof rerenderFn === 'function') rerenderFn();
            closeOverlay();
        });
        footer.appendChild(ok);
        panel.appendChild(footer);

        overlay.appendChild(panel);
        document.body.appendChild(overlay);
    }

    function _legendCloseObjectTree() {
        if (legendObjectTreeOverlayEl && legendObjectTreeOverlayEl.parentNode) {
            legendObjectTreeOverlayEl.parentNode.removeChild(legendObjectTreeOverlayEl);
        }
        legendObjectTreeOverlayEl = null;
    }

    function _legendOpenObjectTree(rerenderFn) {
        _legendCloseObjectTree();
        var overlay = document.createElement('div');
        overlay.className = 'tv-settings-overlay';
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) _legendCloseObjectTree();
        });
        overlay.addEventListener('mousedown', function(e) { e.stopPropagation(); });
        overlay.addEventListener('wheel', function(e) { e.stopPropagation(); });

        var panel = document.createElement('div');
        panel.className = 'tv-settings-panel';
        panel.style.cssText = 'width:540px;max-width:calc(100% - 40px);max-height:78vh;display:flex;flex-direction:column;';

        var header = document.createElement('div');
        header.className = 'tv-settings-header';
        header.style.cssText = 'position:relative;display:flex;align-items:center;gap:8px;';
        var title = document.createElement('h3');
        title.textContent = 'Object tree';
        header.appendChild(title);
        var closeBtn = document.createElement('button');
        closeBtn.className = 'tv-settings-close';
        closeBtn.innerHTML = '<svg viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>';
        closeBtn.addEventListener('click', _legendCloseObjectTree);
        header.appendChild(closeBtn);
        panel.appendChild(header);

        var body = document.createElement('div');
        body.className = 'tv-settings-body';
        body.style.cssText = 'flex:1;overflow-y:auto;';

        _legendNormalizeSeriesOrder();
        var ordered = (entry._legendSeriesOrder || []).slice();
        for (var i = 0; i < ordered.length; i++) {
            (function(sid) {
                var row = document.createElement('div');
                row.className = 'tv-settings-row tv-settings-row-spaced';
                row.style.alignItems = 'center';

                var lbl = document.createElement('span');
                lbl.style.cssText = 'flex:1;color:var(--pywry-tvchart-text);';
                lbl.textContent = _legendSeriesLabel(sid);
                row.appendChild(lbl);

                var vis = document.createElement('input');
                vis.type = 'checkbox';
                vis.className = 'ts-checkbox';
                vis.checked = !(legendUiState.seriesHidden && legendUiState.seriesHidden[sid]);
                vis.addEventListener('change', function() {
                    _legendApplySeriesHidden(sid, !vis.checked);
                    _legendApplySeriesIntervalVisibility(sid);
                    if (typeof rerenderFn === 'function') rerenderFn();
                });
                row.appendChild(vis);

                var rm = document.createElement('button');
                rm.className = 'ts-btn-cancel';
                rm.style.padding = '4px 10px';
                rm.textContent = 'Remove';
                rm.addEventListener('click', function() {
                    if (window.pywry && typeof window.pywry.emit === 'function') {
                        window.pywry.emit('tvchart:remove-series', { chartId: chartId, seriesId: sid });
                    }
                    _legendCloseObjectTree();
                });
                row.appendChild(rm);
                body.appendChild(row);
            })(ordered[i]);
        }

        panel.appendChild(body);
        overlay.appendChild(panel);
        document.body.appendChild(overlay);
        legendObjectTreeOverlayEl = overlay;
    }

    function _legendDisableVolume() {
        if (typeof window._tvBuildCurrentSettings === 'function' && typeof window._tvApplySettingsToChart === 'function') {
            var settings = window._tvBuildCurrentSettings(entry);
            settings['Volume'] = false;
            window._tvApplySettingsToChart(chartId, entry, settings);
        } else {
            var volSeries = entry.volumeMap && entry.volumeMap.main ? entry.volumeMap.main : null;
            if (volSeries) {
                try { entry.chart.removeSeries(volSeries); } catch (e) {}
                delete entry.volumeMap.main;
            }
        }
        legendUiState.volumeHidden = false;
    }

    function _legendEnableVolume() {
        if (typeof window._tvBuildCurrentSettings === 'function' && typeof window._tvApplySettingsToChart === 'function') {
            var settings = window._tvBuildCurrentSettings(entry);
            settings['Volume'] = true;
            window._tvApplySettingsToChart(chartId, entry, settings);
        }
        legendUiState.volumeHidden = false;
    }

    function _legendSetDatasetFlag(key, enabled) {
        var ds = _legendDataset();
        if (!ds) return;
        ds[key] = enabled ? '1' : '0';
    }

    function _legendCopyText(text) {
        var value = String(text || '').trim();
        if (!value) return;
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(value);
            }
        } catch (e) {}
    }

    function _legendCloseSecurityInfo() {
        if (legendSecurityInfoOverlayEl && legendSecurityInfoOverlayEl.parentNode) {
            legendSecurityInfoOverlayEl.parentNode.removeChild(legendSecurityInfoOverlayEl);
        }
        legendSecurityInfoOverlayEl = null;
    }

    function _legendSecurityTickSize(info) {
        var minmov = Number(info && info.minmov);
        var pricescale = Number(info && info.pricescale);
        if (isFinite(minmov) && isFinite(pricescale) && pricescale > 0) {
            return String(minmov / pricescale);
        }
        return '0.01';
    }

    function _legendSecurityExchange(rawSymbol, info) {
        if (info && info.exchange) return String(info.exchange);
        var symbol = String(rawSymbol || '').trim();
        if (symbol.indexOf(':') >= 0) return symbol.split(':')[0].trim().toUpperCase();
        return 'Cboe One';
    }

    function _legendOpenSecurityInfo(seriesId) {
        _legendCloseSecurityInfo();
        var sid = String(seriesId || '');
        if (!sid) return;
        var info = (entry && entry._compareSymbolInfo && entry._compareSymbolInfo[sid])
            ? entry._compareSymbolInfo[sid]
            : (entry && entry._resolvedSymbolInfo && entry._resolvedSymbolInfo[sid])
                ? entry._resolvedSymbolInfo[sid]
                : {};
        var label = _legendSeriesLabel(sid);
        var rawSymbol = (entry && entry._compareSymbols && entry._compareSymbols[sid]) ? entry._compareSymbols[sid] : label;

        var name = String(info.ticker || info.displaySymbol || label || '').trim() || 'Unknown';
        var description = String(info.fullName || info.description || '').trim() || 'Unavailable';
        var type = String(info.type || 'Stock').trim() || 'Stock';
        var pointValue = (info.pointValue != null && info.pointValue !== '') ? String(info.pointValue) : '\u2014';
        var sector = String(info.sector || '').trim();
        var industry = String(info.industry || '').trim();
        var listedExchange = String(info.listed_exchange || info.exchange || '').trim();
        var exchange = String(info.exchange || '').trim();
        var currency = String(info.currency_code || info.currency || 'USD').trim() || 'USD';
        var tickSize = _legendSecurityTickSize(info);
        var timezone = String(info.timezone || 'America/New_York').trim();
        var session = String(info.session || '24x7').trim();
        var sessionPre = String(info.session_premarket || '').trim();
        var sessionReg = String(info.session_regular || '').trim();
        var sessionPost = String(info.session_postmarket || '').trim();

        var sessionSchedule = info.session_schedule || null;

        function _timezoneLabel(tz) {
            var raw = String(tz || '').trim();
            if (!raw || raw === 'UTC' || raw === 'Etc/UTC') return 'UTC';
            try {
                var now = new Date();
                var parts = now.toLocaleString('en-US', { timeZone: raw, timeZoneName: 'shortOffset' }).split(' ');
                var offset = parts[parts.length - 1] || '';
                var city = raw.split('/').pop().replace(/_/g, ' ');
                return city + ' (' + offset + ')';
            } catch (e) {
                return raw;
            }
        }

        function _parseHHMM(s) {
            var m = s.match(/^(\d{2})(\d{2})$/);
            if (!m) return NaN;
            return parseInt(m[1], 10) + parseInt(m[2], 10) / 60;
        }

        function _sessionWindows() {
            // Returns { DAY: [ { from, to, kind } ] } using sessionPre/Reg/Post
            var out = { SUN: [], MON: [], TUE: [], WED: [], THU: [], FRI: [], SAT: [] };
            var weekdays = ['MON', 'TUE', 'WED', 'THU', 'FRI'];
            var allDays = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];

            function addWindow(windowStr, kind, days) {
                var parts = windowStr.split('-');
                if (parts.length !== 2) return;
                var sh = _parseHHMM(parts[0]);
                var eh = _parseHHMM(parts[1]);
                if (isNaN(sh) || isNaN(eh) || eh <= sh) return;
                for (var d = 0; d < days.length; d++) {
                    out[days[d]].push({ from: sh, to: eh, kind: kind });
                }
            }

            // Per-day schedule from symbolInfo (e.g. futures)
            if (sessionSchedule && typeof sessionSchedule === 'object') {
                for (var di = 0; di < allDays.length; di++) {
                    var dayKey = allDays[di];
                    var daySession = sessionSchedule[dayKey];
                    if (!daySession) continue; // Day not in schedule = no trading
                    var segments = String(daySession).split(',');
                    for (var si = 0; si < segments.length; si++) {
                        addWindow(segments[si].trim(), 'regular', [dayKey]);
                    }
                }
                return out;
            }

            // 24x7 markets
            var rawSession = String(session || '').trim().toLowerCase();
            if (rawSession === '24x7' || rawSession === '24/7' || rawSession === '0000-2400') {
                for (var i = 0; i < allDays.length; i++) out[allDays[i]] = [{ from: 0, to: 24, kind: 'regular' }];
                return out;
            }

            if (sessionPre) addWindow(sessionPre, 'pre', weekdays);
            if (sessionReg) addWindow(sessionReg, 'regular', weekdays);
            if (sessionPost) addWindow(sessionPost, 'post', weekdays);

            // Fallback: parse the combined session string if no separate parts
            if (!sessionPre && !sessionReg && !sessionPost) {
                var segments = rawSession.split(',');
                for (var si = 0; si < segments.length; si++) {
                    addWindow(segments[si].trim(), 'regular', weekdays);
                }
            }
            return out;
        }

        function _sessionColorForKind(kind) {
            if (kind === 'pre') return _dimColor;
            if (kind === 'post') return _dimColor;
            return _activeColor;
        }

        function _exchangeWithFlag(exName) {
            var text = String(exName || '').toUpperCase();
            if (text.indexOf('NASDAQ') >= 0 || text.indexOf('NYSE') >= 0 || text.indexOf('CBOE') >= 0 || text.indexOf('OTC') >= 0) {
                return '\uD83C\uDDFA\uD83C\uDDF8 ' + exName;
            }
            if (text.indexOf('LSE') >= 0) return '\uD83C\uDDEC\uD83C\uDDE7 ' + exName;
            if (text.indexOf('TSX') >= 0 || text.indexOf('TSE') >= 0) return '\uD83C\uDDE8\uD83C\uDDE6 ' + exName;
            return String(exName || '');
        }

        var overlay = document.createElement('div');
        overlay.className = 'tv-settings-overlay';
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) _legendCloseSecurityInfo();
        });
        overlay.addEventListener('mousedown', function(e) { e.stopPropagation(); });
        overlay.addEventListener('wheel', function(e) { e.stopPropagation(); });

        var panel = document.createElement('div');
        panel.className = 'tv-settings-panel';
        panel.style.cssText = 'width:760px;max-width:calc(100% - 40px);max-height:84vh;display:flex;flex-direction:column;';

        var header = document.createElement('div');
        header.className = 'tv-settings-header';
        header.style.cssText = 'position:relative;display:flex;align-items:center;gap:8px;padding:18px 28px 14px;';
        var title = document.createElement('h3');
        title.textContent = 'Security Info';
        header.appendChild(title);
        var closeBtn = document.createElement('button');
        closeBtn.className = 'tv-settings-close';
        closeBtn.innerHTML = '<svg viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>';
        closeBtn.addEventListener('click', _legendCloseSecurityInfo);
        header.appendChild(closeBtn);
        panel.appendChild(header);

        var body = document.createElement('div');
        body.className = 'tv-settings-body';
        body.style.cssText = 'flex:1;overflow-y:auto;padding:12px 28px 20px;gap:0;';

        var grid = document.createElement('div');
        grid.style.cssText = 'display:grid;grid-template-columns:minmax(220px,1fr) minmax(220px,1fr);gap:18px 34px;padding:14px 0 20px;border-top:1px solid var(--pywry-tvchart-border-strong);border-bottom:1px solid var(--pywry-tvchart-border-strong);';
        function addInfoCell(caption, value, opt) {
            var cell = document.createElement('div');
            var cap = document.createElement('div');
            cap.style.cssText = 'font-size:12px;font-weight:600;color:var(--pywry-tvchart-text-muted);margin-bottom:4px;text-transform:none;';
            cap.textContent = caption;
            var val = document.createElement('div');
            val.style.cssText = 'font-size:14px;font-family:var(--pywry-font-family);line-height:1.4;color:var(--pywry-tvchart-text);';
            val.textContent = value;
            cell.appendChild(cap);
            cell.appendChild(val);
            grid.appendChild(cell);
        }
        addInfoCell('Name', name);
        addInfoCell('Description', description);
        if (sector) addInfoCell('Sector', sector);
        if (industry) addInfoCell('Industry', industry);
        addInfoCell('Type', type);
        addInfoCell('Point value', pointValue);
        addInfoCell('Listed exchange', _exchangeWithFlag(listedExchange));
        addInfoCell('Exchange', exchange);
        addInfoCell('Currency', currency);
        addInfoCell('Tick size', tickSize);
        body.appendChild(grid);

        var sessionWrap = document.createElement('div');
        sessionWrap.style.cssText = 'padding-top:16px;';
        var sessionTitle = document.createElement('div');
        sessionTitle.style.cssText = 'font-size:12px;font-weight:600;color:var(--pywry-tvchart-text);margin-bottom:12px;';
        sessionTitle.textContent = 'Session';
        sessionWrap.appendChild(sessionTitle);

        var sessionTop = document.createElement('div');
        sessionTop.style.cssText = 'display:flex;align-items:center;justify-content:flex-end;margin-bottom:10px;';
        var allSessions = document.createElement('div');
        allSessions.style.cssText = 'font-size:16px;color:var(--pywry-tvchart-text);display:flex;align-items:center;gap:8px;padding:6px 10px;border-radius:6px;background:var(--pywry-tvchart-hover);cursor:pointer;user-select:none;';
        var chevronSpan = document.createElement('span');
        chevronSpan.style.cssText = 'opacity:.8;display:inline-block;transition:transform .2s;';
        chevronSpan.textContent = '^';
        allSessions.appendChild(chevronSpan);
        var labelSpan = document.createElement('span');

        // Determine current session label from the chart's active session mode
        var currentSessionMode = (entry && entry._sessionMode) ? String(entry._sessionMode) : '';
        if (!currentSessionMode && typeof _tvPersistedSessionMode !== 'undefined') {
            currentSessionMode = String(_tvPersistedSessionMode || '');
        }
        var currentSessionLabel = 'All sessions';
        if (currentSessionMode === 'RTH') currentSessionLabel = 'Regular trading hours';
        else if (currentSessionMode === 'ETH') currentSessionLabel = 'Extended trading hours';

        // Start collapsed — show the current session label
        labelSpan.textContent = currentSessionLabel;
        allSessions.appendChild(labelSpan);
        sessionTop.appendChild(allSessions);
        sessionWrap.appendChild(sessionTop);

        var sessionChart = document.createElement('div');
        sessionChart.style.cssText = 'position:relative;border-radius:6px;padding:8px 0 12px;overflow:hidden;transition:max-height .25s ease, opacity .2s ease;';

        // Start collapsed
        sessionChart.style.maxHeight = '0px';
        sessionChart.style.opacity = '0';
        chevronSpan.style.transform = 'rotate(180deg)';

        allSessions.addEventListener('click', function() {
            var collapsed = sessionChart.style.maxHeight === '0px';
            if (collapsed) {
                sessionChart.style.maxHeight = sessionChart.scrollHeight + 'px';
                sessionChart.style.opacity = '1';
                chevronSpan.style.transform = '';
                labelSpan.textContent = 'All sessions';
            } else {
                sessionChart.style.maxHeight = '0px';
                sessionChart.style.opacity = '0';
                chevronSpan.style.transform = 'rotate(180deg)';
                labelSpan.textContent = currentSessionLabel;
            }
        });
        var dayRows = _sessionWindows();
        var order = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];

        for (var di = 0; di < order.length; di++) {
            var day = order[di];
            var row = document.createElement('div');
            row.style.cssText = 'display:flex;align-items:center;gap:14px;margin:0 0 8px 0;';
            var dlab = document.createElement('div');
            dlab.style.cssText = 'width:36px;font-size:12px;color:var(--pywry-tvchart-text-muted);';
            dlab.textContent = day;
            row.appendChild(dlab);
            var track = document.createElement('div');
            track.style.cssText = 'position:relative;flex:1;height:10px;border-radius:999px;background:color-mix(in srgb, var(--pywry-tvchart-border-strong) 70%, transparent 30%);overflow:hidden;';
            var windows = dayRows[day] || [];
            for (var wi = 0; wi < windows.length; wi++) {
                var w = windows[wi];
                var from = Math.max(0, Math.min(24, Number(w.from || 0)));
                var to = Math.max(0, Math.min(24, Number(w.to || 0)));
                if (to <= from) continue;
                var seg = document.createElement('span');
                var left = (from / 24) * 100;
                var width = ((to - from) / 24) * 100;
                var segColor = _sessionColorForKind(w.kind);
                seg.style.cssText = 'position:absolute;top:0;bottom:0;left:' + left + '%;width:' + width + '%;background:' + segColor + ';opacity:.9;border-radius:999px;';
                track.appendChild(seg);
            }
            row.appendChild(track);
            sessionChart.appendChild(row);
        }

        // "Now" marker — compute from actual exchange time
        var nowPct = 50;
        try {
            var nowStr = new Date().toLocaleString('en-US', { timeZone: timezone, hour12: false, hour: '2-digit', minute: '2-digit' });
            var nowParts = nowStr.split(':');
            var nowH = parseInt(nowParts[0], 10) + parseInt(nowParts[1], 10) / 60;
            nowPct = (nowH / 24) * 100;
        } catch (e) { /* fallback 50% */ }
        var nowLine = document.createElement('div');
        nowLine.style.cssText = 'position:absolute;top:8px;bottom:24px;left:calc(50px + ' + nowPct + '% * (1 - 50px / 100%));width:2px;background:var(--pywry-tvchart-active-text);opacity:0.6;border-radius:1px;pointer-events:none;';
        // Approximate: account for the label offset
        var trackAreaPct = nowPct;
        nowLine.style.left = 'calc(50px + (100% - 50px) * ' + (trackAreaPct / 100) + ')';
        sessionChart.appendChild(nowLine);

        var axis = document.createElement('div');
        axis.style.cssText = 'display:flex;justify-content:space-between;padding-left:50px;padding-right:0;font-size:11px;color:var(--pywry-tvchart-text-muted);margin-top:4px;';
        axis.innerHTML = '<span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span>';
        sessionChart.appendChild(axis);

        // Server time
        var serverTime = document.createElement('div');
        serverTime.style.cssText = 'font-size:13px;color:var(--pywry-tvchart-text-muted);text-align:center;margin-top:8px;';
        try {
            var st = new Date().toLocaleString('en-US', { timeZone: timezone, hour12: true, hour: 'numeric', minute: '2-digit', second: '2-digit' });
            serverTime.textContent = 'Server time: ' + st;
        } catch (e) {
            serverTime.textContent = '';
        }
        sessionChart.appendChild(serverTime);

        var timezoneValue = document.createElement('div');
        timezoneValue.style.cssText = 'font-size:13px;color:var(--pywry-tvchart-text-muted);text-align:center;';
        timezoneValue.textContent = 'Exchange timezone: ' + _timezoneLabel(timezone);
        sessionChart.appendChild(timezoneValue);
        sessionWrap.appendChild(sessionChart);
        body.appendChild(sessionWrap);

        panel.appendChild(body);
        overlay.appendChild(panel);
        document.body.appendChild(overlay);
        legendSecurityInfoOverlayEl = overlay;
    }

    function _legendInstallControls() {
        if (mainCtrlEl && !mainCtrlEl.dataset.bound) {
            mainCtrlEl.dataset.bound = '1';
            var mainEyeBtn = _legendMakeButton('Hide', hideSvg, function(btn) {
                _legendApplyMainHidden(!legendUiState.mainHidden);
                btn.setAttribute('data-tooltip', legendUiState.mainHidden ? 'Show' : 'Hide');
                btn.setAttribute('aria-label', legendUiState.mainHidden ? 'Show' : 'Hide');
                btn.innerHTML = legendUiState.mainHidden ? showSvg : hideSvg;
            });
            mainEyeBtn.id = 'tvchart-main-eye-' + chartId;
            mainCtrlEl.appendChild(mainEyeBtn);
            mainCtrlEl.appendChild(_legendMakeButton('Settings', settingsSvg, function() {
                if (typeof window._tvShowChartSettings === 'function') {
                    window._tvShowChartSettings(chartId);
                }
            }));
            mainCtrlEl.appendChild(_legendMakeButton('Remove', removeSvg, function() {
                _legendApplyMainHidden(true);
            }));
            mainCtrlEl.appendChild(_legendMakeButton('More', menuSvg, function(btn) {
                var ds = _legendDataset() || {};
                var showValues = _legendBool(ds, 'showStatusValues', true);
                var symbolName = (ds && ds.baseTitle) ? String(ds.baseTitle) : '';
                _legendOpenMenu(btn, [
                    {
                        label: 'Security info...',
                        icon: infoSvg,
                        run: function() { _legendOpenSecurityInfo('main'); },
                    },
                    {
                        label: legendUiState.mainHidden ? 'Show' : 'Hide',
                        icon: legendUiState.mainHidden ? showSvg : hideSvg,
                        run: function() {
                            _legendApplyMainHidden(!legendUiState.mainHidden);
                            var eb = document.getElementById('tvchart-main-eye-' + chartId);
                            if (eb) {
                                eb.setAttribute('data-tooltip', legendUiState.mainHidden ? 'Show' : 'Hide');
                                eb.setAttribute('aria-label', legendUiState.mainHidden ? 'Show' : 'Hide');
                                eb.innerHTML = legendUiState.mainHidden ? showSvg : hideSvg;
                            }
                        },
                    },
                    {
                        label: 'Settings',
                        icon: settingsSvg,
                        run: function() {
                            if (typeof window._tvShowChartSettings === 'function') {
                                window._tvShowChartSettings(chartId);
                            }
                        },
                    },
                    {
                        label: 'Remove',
                        icon: removeSvg,
                        run: function() { _legendApplyMainHidden(true); },
                    },
                    { separator: true },
                    {
                        label: showValues ? 'Hide Values' : 'Show Values',
                        icon: valuesSvg,
                        meta: showValues ? 'On' : 'Off',
                        run: function() {
                            _legendSetDatasetFlag('showStatusValues', !showValues);
                            _legendRenderMainFromLastData();
                        },
                    },
                    {
                        label: 'Copy Symbol',
                        icon: copySvg,
                        meta: symbolName || 'Unavailable',
                        disabled: !symbolName,
                        tooltip: symbolName || 'Symbol name unavailable',
                        run: function() { _legendCopyText(symbolName); },
                    },
                ]);
            }));
        }
        if (volCtrlEl && !volCtrlEl.dataset.bound) {
            volCtrlEl.dataset.bound = '1';
            var volEyeBtn = _legendMakeButton('Hide', hideSvg, function(btn) {
                _legendApplyVolumeHidden(!legendUiState.volumeHidden);
                btn.setAttribute('data-tooltip', legendUiState.volumeHidden ? 'Show' : 'Hide');
                btn.setAttribute('aria-label', legendUiState.volumeHidden ? 'Show' : 'Hide');
                btn.innerHTML = legendUiState.volumeHidden ? showSvg : hideSvg;
            });
            volEyeBtn.id = 'tvchart-vol-eye-' + chartId;
            volCtrlEl.appendChild(volEyeBtn);
            volCtrlEl.appendChild(_legendMakeButton('Settings', settingsSvg, function() {
                if (typeof window._tvShowVolumeSettings === 'function') {
                    window._tvShowVolumeSettings(chartId);
                }
            }));
            volCtrlEl.appendChild(_legendMakeButton('Remove', removeSvg, function() {
                _legendDisableVolume();
            }));
            volCtrlEl.appendChild(_legendMakeButton('More', menuSvg, function(btn) {
                var hasVolumeSeries = !!(entry.volumeMap && entry.volumeMap.main);
                var ds = _legendDataset() || {};
                var showVolume = _legendBool(ds, 'showVolume', hasVolumeSeries);
                _legendOpenMenu(btn, [
                    {
                        label: legendUiState.volumeHidden ? 'Show' : 'Hide',
                        icon: legendUiState.volumeHidden ? showSvg : hideSvg,
                        run: function() {
                            _legendApplyVolumeHidden(!legendUiState.volumeHidden);
                            var eb = document.getElementById('tvchart-vol-eye-' + chartId);
                            if (eb) {
                                eb.setAttribute('data-tooltip', legendUiState.volumeHidden ? 'Show' : 'Hide');
                                eb.setAttribute('aria-label', legendUiState.volumeHidden ? 'Show' : 'Hide');
                                eb.innerHTML = legendUiState.volumeHidden ? showSvg : hideSvg;
                            }
                        },
                    },
                    {
                        label: 'Settings',
                        icon: settingsSvg,
                        run: function() {
                            if (typeof window._tvShowVolumeSettings === 'function') {
                                window._tvShowVolumeSettings(chartId);
                            }
                        },
                    },
                    {
                        label: 'Remove',
                        icon: removeSvg,
                        run: function() { _legendDisableVolume(); },
                    },
                    { separator: true },
                    {
                        label: showVolume ? 'Hide Volume Label' : 'Show Volume Label',
                        icon: valuesSvg,
                        meta: showVolume ? 'On' : 'Off',
                        run: function() {
                            _legendSetDatasetFlag('showVolume', !showVolume);
                        },
                    },
                    {
                        label: 'Restore Volume',
                        icon: valuesSvg,
                        disabled: hasVolumeSeries,
                        meta: hasVolumeSeries ? 'Active' : 'Removed',
                        run: function() { _legendEnableVolume(); },
                    },
                ]);
            }));
        }
    }

    _legendInstallControls();

    // -- Indicator legend collapse/expand chevron ----------------------------
    var _indCollapseBtn = scopedById('tvchart-legend-collapse');
    var _indBox = scopedById('tvchart-legend-indicators');
    var _chevronDown = '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:block"><polyline points="4,6 8,10 12,6"/></svg>';
    var _chevronUp = '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:block"><polyline points="4,10 8,6 12,10"/></svg>';

    function _legendUpdateCollapseBtn() {
        if (!_indCollapseBtn) return;
        // Show the toggle when there's any content below the main OHLC row
        var hasIndicators = _indBox && _indBox.children.length > 0;
        _indCollapseBtn.style.display = hasIndicators ? 'flex' : 'none';
        var collapsed = !!legendUiState.indicatorsCollapsed;
        _indCollapseBtn.innerHTML = collapsed ? _chevronDown : _chevronUp;
        _indCollapseBtn.setAttribute('data-tooltip', collapsed ? 'Show indicator legend' : 'Hide indicator legend');
        _indCollapseBtn.setAttribute('aria-label', collapsed ? 'Show indicator legend' : 'Hide indicator legend');
        _indCollapseBtn.classList.toggle('is-collapsed', collapsed);
        if (_indBox) _indBox.style.display = collapsed ? 'none' : '';
    }

    if (_indCollapseBtn) {
        _indCollapseBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            legendUiState.indicatorsCollapsed = !legendUiState.indicatorsCollapsed;
            _legendUpdateCollapseBtn();
        });
    }

    // Watch for indicator rows being added/rebuilt
    if (_indBox) {
        var _indObserver = new MutationObserver(function() { _legendUpdateCollapseBtn(); });
        _indObserver.observe(_indBox, { childList: true });
    }
    _legendUpdateCollapseBtn();

    function _legendBool(ds, key, defaultVal) {
        if (!ds || ds[key] == null) return defaultVal;
        return ds[key] !== '0';
    }

    function _legendDataset() {
        var box = scopedById('tvchart-legend-box');
        return box ? box.dataset : null;
    }

    function _legendTitleBase(ds) {
        var base = (ds && ds.baseTitle) ? ds.baseTitle : '';
        if (!base && entry && entry.payload && entry.payload.useDatafeed && entry.payload.series && entry.payload.series[0] && entry.payload.series[0].symbol) {
            base = String(entry.payload.series[0].symbol);
        }
        if (!base && entry && entry.payload && entry.payload.title) {
            base = String(entry.payload.title);
        }
        if (!base && entry && entry.payload && entry.payload.series && entry.payload.series[0] && entry.payload.series[0].seriesId) {
            var s0 = String(entry.payload.series[0].seriesId);
            if (s0 && s0 !== 'main') base = s0;
        }
        if (!base) base = (mainKey === 'main' ? '' : mainKey);
        // Description mode replaces the base title with resolved symbol info
        if (ds && ds.description && ds.description !== 'Off') {
            var descMode = ds.description;
            var symInfo = (entry && entry._resolvedSymbolInfo && entry._resolvedSymbolInfo.main)
                || (entry && entry._mainSymbolInfo) || {};
            var ticker = String(symInfo.ticker || symInfo.displaySymbol || symInfo.symbol || base || '').trim();
            var descText = String(symInfo.description || symInfo.fullName || '').trim();
            if (descMode === 'Description' && descText) {
                base = descText;
            } else if (descMode === 'Ticker and description') {
                base = (ticker && descText) ? (ticker + ' · ' + descText) : (ticker || descText || base);
            }
            // 'Ticker' mode keeps base as-is (it's already the ticker)
        }
        if (_legendBool(ds, 'showLogo', false)) {
            base = (base ? '◉ ' + base : '◉');
        }
        if (_legendBool(ds, 'showTitle', true) === false) {
            return '';
        }
        if (ds && ds.interval && base) {
            base = base + ' · ' + ds.interval;
        }
        return base;
    }

    function _legendEscape(text) {
        return String(text || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function _legendColorForSeries(seriesId, dataPoint, ds) {
        var sid = String(seriesId || 'main');
        if (entry && entry._legendSeriesColors && entry._legendSeriesColors[sid]) {
            return String(entry._legendSeriesColors[sid]);
        }
        if (dataPoint && dataPoint.open !== undefined) {
            return colorize(dataPoint.close, dataPoint.open);
        }
        return (ds && ds.lineColor) ? ds.lineColor : _sessionBreaksColor;
    }

    function _legendLastSeriesValue(seriesId) {
        var sid = String(seriesId || 'main');
        var rows = entry && entry._seriesRawData ? entry._seriesRawData[sid] : null;
        if (!rows || !rows.length) return null;
        var last = rows[rows.length - 1] || {};
        if (last.close !== undefined && last.close !== null) return Number(last.close);
        if (last.value !== undefined && last.value !== null) return Number(last.value);
        return null;
    }

    function _legendRenderSeriesRows(param) {
        if (!seriesEl) return;
        var ds = _legendDataset() || {};
        var currentSeriesKeys = Object.keys(entry.seriesMap || {});
        var currentMainKey = (currentSeriesKeys.indexOf('main') >= 0)
            ? 'main'
            : (currentSeriesKeys[0] || mainKey);

        var htmlParts = [];
        for (var i = 0; i < currentSeriesKeys.length; i++) {
            var sid = currentSeriesKeys[i];
            if (String(sid) === String(currentMainKey)) continue;
            if (String(sid) === 'volume') continue;
            if (String(sid).indexOf('ind_') === 0) continue;

            var sApi = entry.seriesMap[sid];
            if (!sApi) continue;
            var d = _legendResolveHoveredPoint(sid, sApi, param);
            var value = null;
            if (d && d.open !== undefined) {
                value = Number(d.close);
            } else if (d && d.value !== undefined) {
                value = Number(d.value);
            } else {
                value = _legendLastSeriesValue(sid);
            }

            var label = _legendSeriesLabel(sid);
            var color = _legendColorForSeries(sid, d, ds);
            var rowHidden = !!(legendUiState.seriesHidden && legendUiState.seriesHidden[sid]);
            htmlParts.push(
                '<div class="tvchart-legend-row tvchart-legend-series-row" data-series-id="' + _legendEscape(sid) + '" data-hidden="' + (rowHidden ? '1' : '0') + '">' +
                '<span class="tvchart-legend-series-dot" style="background:' + _legendEscape(color) + '"></span>' +
                '<span class="tvchart-legend-series-name">' + _legendEscape(label) + '</span>' +
                '<span class="tvchart-legend-series-value" style="color:' + _legendEscape(color) + '">' + _legendEscape(value == null ? '--' : fmt(value)) + '</span>' +
                '<span class="tvchart-legend-row-actions tvchart-legend-series-actions">' +
                '<button type="button" class="tvchart-legend-btn tvchart-legend-series-btn" data-series-id="' + _legendEscape(sid) + '" data-action="hide" data-tooltip="' + (rowHidden ? 'Show' : 'Hide') + '">' + (rowHidden ? showSvg : hideSvg) + '</button>' +
                '<button type="button" class="tvchart-legend-btn tvchart-legend-series-btn" data-series-id="' + _legendEscape(sid) + '" data-action="settings" data-tooltip="Settings">' + settingsSvg + '</button>' +
                '<button type="button" class="tvchart-legend-btn tvchart-legend-series-btn" data-series-id="' + _legendEscape(sid) + '" data-action="remove" data-tooltip="Remove">' +
                '<svg viewBox="0 0 16 16" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" style="display:block"><line x1="4" y1="4" x2="12" y2="12"/><line x1="12" y1="4" x2="4" y2="12"/></svg>' +
                '</button>' +
                '<button type="button" class="tvchart-legend-btn tvchart-legend-series-btn" data-series-id="' + _legendEscape(sid) + '" data-action="more" data-tooltip="More">' + menuSvg + '</button>' +
                '</span>' +
                '</div>'
            );
        }

        _legendNormalizeSeriesOrder();
        if (entry._legendSeriesOrder && entry._legendSeriesOrder.length) {
            var orderMap = {};
            for (var oi = 0; oi < entry._legendSeriesOrder.length; oi++) {
                orderMap[entry._legendSeriesOrder[oi]] = oi;
            }
            htmlParts.sort(function(a, b) {
                var ma = a.match(/data-series-id="([^"]+)"/);
                var mb = b.match(/data-series-id="([^"]+)"/);
                var sa = ma ? ma[1] : '';
                var sb = mb ? mb[1] : '';
                var ia = (orderMap[sa] != null) ? orderMap[sa] : 9999;
                var ib = (orderMap[sb] != null) ? orderMap[sb] : 9999;
                return ia - ib;
            });
        }

        seriesEl.innerHTML = htmlParts.join('');
        seriesEl.style.display = htmlParts.length ? 'block' : 'none';

        var actionButtons = seriesEl.querySelectorAll('.tvchart-legend-series-btn');
        for (var bi = 0; bi < actionButtons.length; bi++) {
            actionButtons[bi].addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                var targetSeriesId = this.getAttribute('data-series-id') || '';
                if (!targetSeriesId) return;
                var action = this.getAttribute('data-action') || '';
                if (action === 'hide') {
                    var nextHidden = !(legendUiState.seriesHidden && legendUiState.seriesHidden[targetSeriesId]);
                    _legendApplySeriesHidden(targetSeriesId, nextHidden);
                    _legendRenderSeriesRows(param || null);
                    return;
                }
                if (action === 'settings') {
                    if (typeof window._tvShowSeriesSettings === 'function') {
                        window._tvShowSeriesSettings(chartId, targetSeriesId);
                    }
                    return;
                }
                if (action === 'remove') {
                    if (window.pywry && typeof window.pywry.emit === 'function') {
                        window.pywry.emit('tvchart:remove-series', { chartId: chartId, seriesId: targetSeriesId });
                    }
                    return;
                }
                if (action === 'more') {
                    var rowLabel = _legendSeriesLabel(targetSeriesId);
                    var rowHidden = !!(legendUiState.seriesHidden && legendUiState.seriesHidden[targetSeriesId]);
                    var currentScale = _legendGetSeriesScale(targetSeriesId);
                    var menuAnchor = this;
                    _legendOpenMenu(this, [
                        {
                            label: 'Security info...',
                            icon: infoSvg,
                            run: function() { _legendOpenSecurityInfo(targetSeriesId); },
                        },
                        {
                            label: 'Visual order',
                            icon: layersSvg,
                            meta: '>',
                            run: function() {
                                _legendOpenMenu(menuAnchor, [
                                    {
                                        label: 'Bring to front',
                                        icon: layersSvg,
                                        run: function() {
                                            _legendMoveSeriesOrder(targetSeriesId, 'top');
                                            _legendRenderSeriesRows(param || null);
                                        },
                                    },
                                    {
                                        label: 'Send to back',
                                        icon: layersSvg,
                                        run: function() {
                                            _legendMoveSeriesOrder(targetSeriesId, 'bottom');
                                            _legendRenderSeriesRows(param || null);
                                        },
                                    },
                                    {
                                        label: 'Move up',
                                        icon: layersSvg,
                                        run: function() {
                                            _legendMoveSeriesOrder(targetSeriesId, 'up');
                                            _legendRenderSeriesRows(param || null);
                                        },
                                    },
                                    {
                                        label: 'Move down',
                                        icon: layersSvg,
                                        run: function() {
                                            _legendMoveSeriesOrder(targetSeriesId, 'down');
                                            _legendRenderSeriesRows(param || null);
                                        },
                                    },
                                ]);
                            },
                        },
                        {
                            label: 'Visibility on intervals',
                            icon: intervalSvg,
                            meta: '>',
                            run: function() {
                                _legendOpenVisibilityIntervalsDialog(targetSeriesId, function() {
                                    _legendRenderSeriesRows(param || null);
                                });
                            },
                        },
                        {
                            label: 'Move to',
                            icon: moveSvg,
                            meta: '>',
                            run: function() {
                                _legendOpenMenu(menuAnchor, [
                                    {
                                        label: 'Right scale',
                                        icon: pinSvg,
                                        run: function() {
                                            _legendSetSeriesScale(targetSeriesId, 'right');
                                            _legendRenderSeriesRows(param || null);
                                        },
                                    },
                                    {
                                        label: 'Left scale',
                                        icon: pinSvg,
                                        run: function() {
                                            _legendSetSeriesScale(targetSeriesId, 'left');
                                            _legendRenderSeriesRows(param || null);
                                        },
                                    },
                                    {
                                        label: 'No scale',
                                        icon: pinSvg,
                                        run: function() {
                                            _legendSetSeriesScale(targetSeriesId, 'none');
                                            _legendRenderSeriesRows(param || null);
                                        },
                                    },
                                ]);
                            },
                        },
                        {
                            label: 'Pin to scale (now ' + currentScale + ')',
                            icon: pinSvg,
                            meta: '>',
                            run: function() {
                                var next = (currentScale === 'right') ? 'left' : 'right';
                                _legendSetSeriesScale(targetSeriesId, next);
                                _legendRenderSeriesRows(param || null);
                            },
                        },
                        { separator: true },
                        {
                            label: 'Copy',
                            icon: copySvg,
                            meta: 'Ctrl + C',
                            run: function() { _legendCopyText(rowLabel); },
                        },
                        {
                            label: rowHidden ? 'Show' : 'Hide',
                            icon: hideSvg,
                            run: function() {
                                _legendApplySeriesHidden(targetSeriesId, !rowHidden);
                                _legendRenderSeriesRows(param || null);
                            },
                        },
                        {
                            label: 'Remove',
                            icon: removeSvg,
                            meta: 'Del',
                            run: function() {
                                if (window.pywry && typeof window.pywry.emit === 'function') {
                                    window.pywry.emit('tvchart:remove-series', { chartId: chartId, seriesId: targetSeriesId });
                                }
                            },
                        },
                        { separator: true },
                        {
                            label: 'Object tree...',
                            icon: treeSvg,
                            run: function() {
                                _legendOpenObjectTree(function() {
                                    _legendRenderSeriesRows(param || null);
                                });
                            },
                        },
                        { separator: true },
                        {
                            label: 'Settings...',
                            icon: settingsSvg,
                            run: function() {
                                if (typeof window._tvShowSeriesSettings === 'function') {
                                    window._tvShowSeriesSettings(chartId, targetSeriesId);
                                }
                            },
                        },
                    ]);
                }
            });
        }
    }

    function _legendSeriesLabel(seriesId) {
        var sid = String(seriesId || 'main');
        if (sid === 'main') {
            var ds = _legendDataset() || {};
            var base = (ds && ds.baseTitle) ? String(ds.baseTitle) : '';
            if (!base && entry && entry.payload && entry.payload.useDatafeed && entry.payload.series && entry.payload.series[0] && entry.payload.series[0].symbol) {
                base = String(entry.payload.series[0].symbol);
            }
            if (!base && entry && entry.payload && entry.payload.title) {
                base = String(entry.payload.title);
            }
            return base || 'Main';
        }
        if (entry && entry._compareLabels && entry._compareLabels[sid]) {
            return String(entry._compareLabels[sid]);
        }
        if (entry && entry._compareSymbolInfo && entry._compareSymbolInfo[sid]) {
            var info = entry._compareSymbolInfo[sid] || {};
            var display = String(info.displaySymbol || info.ticker || '').trim();
            if (display) return display.toUpperCase();
            var full = String(info.fullName || '').trim();
            if (full) return full;
            var infoSymbol = String(info.symbol || '').trim();
            if (infoSymbol) {
                return infoSymbol.indexOf(':') >= 0
                    ? infoSymbol.split(':').pop().trim().toUpperCase()
                    : infoSymbol.toUpperCase();
            }
        }
        if (entry && entry._compareSymbols && entry._compareSymbols[sid]) {
            var raw = String(entry._compareSymbols[sid]);
            return raw.indexOf(':') >= 0 ? raw.split(':').pop().trim().toUpperCase() : raw.toUpperCase();
        }
        return sid;
    }

    function _legendIsIntraday() {
        if (typeof _tvIsCurrentIntervalIntraday === 'function') {
            return _tvIsCurrentIntervalIntraday();
        }
        var interval = (typeof _tvCurrentInterval === 'function') ? _tvCurrentInterval(chartId) : '';
        var raw = String(interval || '').trim().toLowerCase();
        if (!raw || raw === '1d' || raw === '1w' || raw === '1m') return false;
        if (/^\d+$/.test(raw)) return true;
        if (/^\d+[smh]$/i.test(raw)) return true;
        return false;
    }

    function _legendGetTimezone() {
        var info = entry && entry._resolvedSymbolInfo && entry._resolvedSymbolInfo.main;
        return (info && info.timezone) ? String(info.timezone).trim() : 'America/New_York';
    }

    function _legendFormatBarTime(timeValue) {
        if (timeValue == null) return '';
        if (!_legendIsIntraday()) return '';
        var ts;
        if (typeof timeValue === 'number') {
            ts = timeValue;
        } else if (typeof timeValue === 'object' && typeof timeValue.timestamp === 'number') {
            ts = timeValue.timestamp;
        } else {
            return '';
        }
        // ts is epoch seconds
        var date = new Date(ts * 1000);
        var tz = _legendGetTimezone();
        try {
            return date.toLocaleString('en-US', {
                timeZone: tz,
                hour: '2-digit',
                minute: '2-digit',
                hour12: false
            });
        } catch (e) {
            var h = date.getUTCHours();
            var m = date.getUTCMinutes();
            return (h < 10 ? '0' : '') + h + ':' + (m < 10 ? '0' : '') + m;
        }
    }

    function _legendRenderMainFromLastData() {
        if (!ohlcEl) return;
        var ds = _legendDataset() || {};
        if (!_legendBool(ds, 'showStatusValues', true)) {
            ohlcEl.innerHTML = '';
            return;
        }
        var highLowMode = ds.highLowMode || 'Hidden';
        var highLowColor = ds.highLowColor || _downColor;
        var lineColor = ds.lineColor || _upColor;
        var symbolMode = ds.symbolMode || 'Value, line';

        var currentSeriesKeys = Object.keys(entry.seriesMap || {});
        var currentMainKey = (currentSeriesKeys.indexOf('main') >= 0)
            ? 'main'
            : (currentSeriesKeys[0] || mainKey);
        var rows = entry && entry._seriesRawData ? entry._seriesRawData[currentMainKey] : null;
        if (!rows || !rows.length) {
            ohlcEl.innerHTML = '';
            return;
        }

        var last = rows[rows.length - 1] || {};
        if (last.open !== undefined) {
            var chg = Number(last.close) - Number(last.open);
            var chgPct = Number(last.open) !== 0 ? ((chg / Number(last.open)) * 100) : 0;
            var clr = colorize(last.close, last.open);
            var parts = [];
            var barTime = _legendFormatBarTime(last.time);
            if (barTime) parts.push('<span style="color:var(--pywry-tvchart-text-dim)">' + barTime + '</span>');
            if (symbolMode !== 'Line only') {
                parts.push('<span style="color:var(--pywry-tvchart-text-dim)">O</span> <span style="color:' + clr + '">' + fmt(last.open) + '</span>');
                if (highLowMode !== 'Hidden') {
                    parts.push('<span style="color:' + highLowColor + '">H</span> <span style="color:' + clr + '">' + fmt(last.high) + '</span>');
                    parts.push('<span style="color:' + highLowColor + '">L</span> <span style="color:' + clr + '">' + fmt(last.low) + '</span>');
                }
                parts.push('<span style="color:var(--pywry-tvchart-text-dim)">C</span> <span style="color:' + clr + '">' + fmt(last.close) + '</span>');
            } else {
                parts.push('<span style="color:' + lineColor + '">—</span>');
            }
            if (_legendBool(ds, 'showBarChange', true)) {
                parts.push('<span style="color:' + clr + '">' + (chg >= 0 ? '+' : '') + fmt(chg) +
                    ' (' + (chg >= 0 ? '+' : '') + chgPct.toFixed(2) + '%)</span>');
            }
            // Append volume on the same OHLC line (like TradingView)
            var _volSr = entry.volumeMap && entry.volumeMap.main ? entry.volumeMap.main : entry.seriesMap['volume'];
            var _volPr = (entry && entry._volumeColorPrefs) || {};
            var _volSl = _volPr.valuesInStatusLine !== false;
            if (_legendBool(ds, 'showVolume', !!_volSr) && _volSl && _volSr) {
                var volRows = entry._seriesRawData ? entry._seriesRawData['volume'] : null;
                if (volRows && volRows.length) {
                    var lastVol = volRows[volRows.length - 1];
                    if (lastVol && lastVol.value !== undefined) {
                        parts.push('<span style="color:var(--pywry-tvchart-text-dim)">Vol</span> ' + fmtVol(lastVol.value));
                    }
                }
            }
            ohlcEl.innerHTML = parts.join(' ');
            return;
        }

        if (last.value !== undefined) {
            var barTimeLine = _legendFormatBarTime(last.time);
            var timePrefix = barTimeLine ? '<span style="color:var(--pywry-tvchart-text-dim)">' + barTimeLine + '</span> ' : '';
            ohlcEl.innerHTML = (symbolMode === 'Line only')
                ? timePrefix + '<span style="color:' + lineColor + '">—</span>'
                : timePrefix + '<span style="color:' + lineColor + '">' + fmt(last.value) + '</span>';
            return;
        }

        ohlcEl.innerHTML = '';
    }

    titleEl.textContent = _legendTitleBase(_legendDataset());
    titleEl.style.display = titleEl.textContent ? 'inline-flex' : 'none';
    _legendRenderMainFromLastData();
    _legendRenderSeriesRows(null);
    // Initial vol row setup
    if (volRowEl) {
        var _ds0 = _legendDataset() || {};
        var _vsr0 = entry.volumeMap && entry.volumeMap.main ? entry.volumeMap.main : entry.seriesMap['volume'];
        var _showVol0 = _legendBool(_ds0, 'showVolume', !!_vsr0) && !!_vsr0;
        // In datafeed (UDF) mode, volume loads asynchronously — start visible
        // so control buttons appear immediately. The legend-refresh event
        // from the datafeed or crosshair handler will adjust if needed.
        var isDatafeedMode = !!(entry.payload && entry.payload.useDatafeed);
        volRowEl.style.display = (_showVol0 || isDatafeedMode) ? 'flex' : 'none';
        if (volEl) volEl.innerHTML = '<span style="color:var(--pywry-tvchart-text-dim)">Volume</span>';
    }

    window.addEventListener('pywry:legend-refresh', function(ev) {
        var targetChartId = ev && ev.detail && ev.detail.chartId ? String(ev.detail.chartId) : '';
        if (targetChartId && String(targetChartId) !== String(chartId)) {
            return;
        }
        titleEl.textContent = _legendTitleBase(_legendDataset());
        titleEl.style.display = titleEl.textContent ? 'inline-flex' : 'none';
        _legendRenderMainFromLastData();
        _legendRenderSeriesRows(null);
        // Refresh vol row
        if (volRowEl) {
            var _dsR = _legendDataset() || {};
            var _vsrR = entry.volumeMap && entry.volumeMap.main ? entry.volumeMap.main : entry.seriesMap['volume'];
            var _showVolR = _legendBool(_dsR, 'showVolume', !!_vsrR) && !!_vsrR;
            volRowEl.style.display = _showVolR ? 'flex' : 'none';
            if (volEl) volEl.innerHTML = _showVolR ? '<span style="color:var(--pywry-tvchart-text-dim)">Volume</span>' : '';
        }
    });

    entry.chart.subscribeCrosshairMove(function(param) {
        if (!param || param.time == null) {
            // Crosshair left the chart area; show last known values if any
            _legendRenderMainFromLastData();
            _legendRenderSeriesRows(null);
            return;
        }

        var ds = _legendDataset() || {};
        titleEl.textContent = _legendTitleBase(ds);
        titleEl.style.display = titleEl.textContent ? 'inline-flex' : 'none';
        var textColor = ds.textColor || '';
        if (textColor) {
            ohlcEl.style.color = textColor;
            if (volEl) volEl.style.color = textColor;
        } else {
            ohlcEl.style.color = '';
            if (volEl) volEl.style.color = '';
        }

        var highLowMode = ds.highLowMode || 'Hidden';
        var highLowColor = ds.highLowColor || _downColor;
        var lineColor = ds.lineColor || _upColor;
        var symbolMode = ds.symbolMode || 'Value, line';
        var legendMainHtml = '';

        var currentSeriesKeys = Object.keys(entry.seriesMap || {});
        var currentMainKey = (currentSeriesKeys.indexOf('main') >= 0)
            ? 'main'
            : (currentSeriesKeys[0] || mainKey);

        for (var i = 0; i < currentSeriesKeys.length; i++) {
            var sKey = currentSeriesKeys[i];
            var sApi = entry.seriesMap[sKey];
            if (!sApi) continue;
            var d = _legendResolveHoveredPoint(sKey, sApi, param);
            if (!d) continue;
            var isMain = (String(sKey) === String(currentMainKey));

            if (d.open !== undefined) {
                // OHLC(V) bar
                var chg    = d.close - d.open;
                var chgPct = d.open !== 0 ? ((chg / d.open) * 100) : 0;
                var clr    = colorize(d.close, d.open);

                if (isMain) {
                    var parts = [];
                    var barTime = _legendFormatBarTime(param.time);
                    if (barTime) parts.push('<span style="color:var(--pywry-tvchart-text-dim)">' + barTime + '</span>');
                    if (symbolMode !== 'Line only') {
                        parts.push('<span style="color:var(--pywry-tvchart-text-dim)">O</span> <span style="color:' + clr + '">' + fmt(d.open) + '</span>');
                        if (highLowMode !== 'Hidden') {
                            parts.push('<span style="color:' + highLowColor + '">H</span> <span style="color:' + clr + '">' + fmt(d.high) + '</span>');
                            parts.push('<span style="color:' + highLowColor + '">L</span> <span style="color:' + clr + '">' + fmt(d.low) + '</span>');
                        }
                        parts.push('<span style="color:var(--pywry-tvchart-text-dim)">C</span> <span style="color:' + clr + '">' + fmt(d.close) + '</span>');
                    } else {
                        parts.push('<span style="color:' + lineColor + '">—</span>');
                    }
                    if (_legendBool(ds, 'showBarChange', true)) {
                        parts.push('<span style="color:' + clr + '">' + (chg >= 0 ? '+' : '') + fmt(chg) +
                            ' (' + (chg >= 0 ? '+' : '') + chgPct.toFixed(2) + '%)</span>');
                    }
                    // Append volume on the same OHLC line (like TradingView)
                    var _volS = entry.volumeMap && entry.volumeMap.main ? entry.volumeMap.main : entry.seriesMap['volume'];
                    var _volP = (entry && entry._volumeColorPrefs) || {};
                    var _volSL = _volP.valuesInStatusLine !== false;
                    if (_legendBool(ds, 'showVolume', !!_volS) && _volSL && _volS) {
                        var _vd = _legendResolveHoveredPoint('volume', _volS, param);
                        if (_vd && _vd.value !== undefined) {
                            parts.push('<span style="color:var(--pywry-tvchart-text-dim)">Vol</span> ' + fmtVol(_vd.value));
                        }
                    }
                    legendMainHtml = parts.join(' ');
                }
            } else if (d.value !== undefined) {
                // Line/area series
                if (isMain) {
                    var barTimeLine = _legendFormatBarTime(param.time);
                    var timePrefix = barTimeLine ? '<span style="color:var(--pywry-tvchart-text-dim)">' + barTimeLine + '</span> ' : '';
                    if (symbolMode === 'Line only') {
                        legendMainHtml = timePrefix + '<span style="color:' + lineColor + '">—</span>';
                    } else {
                        legendMainHtml = timePrefix + '<span style="color:' + lineColor + '">' + fmt(d.value) + '</span>';
                    }
                }
            }
        }
        ohlcEl.innerHTML = _legendBool(ds, 'showStatusValues', true) ? legendMainHtml : '';
        _legendRenderSeriesRows(param);

        if (mainRowEl) {
            var showMainRow = !!(titleEl.textContent || ohlcEl.textContent || ohlcEl.innerHTML);
            mainRowEl.style.display = showMainRow ? 'flex' : 'none';
            mainRowEl.dataset.hidden = legendUiState.mainHidden ? '1' : '0';
        }

        // Volume value is now shown on the OHLC line above.
        // The separate vol row just shows a "Volume" label + control buttons.
        if (volEl) volEl.innerHTML = '<span style="color:var(--pywry-tvchart-text-dim)">Volume</span>';

        if (volRowEl) {
            // Show the Volume control row if volume subplot is visible
            var _vsr = entry.volumeMap && entry.volumeMap.main ? entry.volumeMap.main : entry.seriesMap['volume'];
            var showVolRow = _legendBool(ds, 'showVolume', !!_vsr) && !!_vsr;
            volRowEl.style.display = showVolRow ? 'flex' : 'none';
            volRowEl.dataset.hidden = legendUiState.volumeHidden ? '1' : '0';
        }
    });
}