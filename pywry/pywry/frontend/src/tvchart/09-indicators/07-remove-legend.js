function _getNextIndicatorColor() {
    var c = _cssVar('--pywry-preset-' + ((_indicatorColorIdx % 10) + 3), _INDICATOR_COLORS[_indicatorColorIdx % _INDICATOR_COLORS.length]);
    _indicatorColorIdx++;
    return c;
}

function _tvRemoveIndicator(seriesId) {
    var info = _activeIndicators[seriesId];
    if (!info) return;
    var chartId = info.chartId;
    var entry = window.__PYWRY_TVCHARTS__[chartId];

    // Push undo entry before removing (skip during layout restore)
    if (!window.__PYWRY_UNDO_SUPPRESS__) {
        var _undoDef = {
            name: info.name, key: info.type,
            defaultPeriod: info.period || 0,
            _color: info.color,
            _multiplier: info.multiplier,
            _maType: info.maType,
            _offset: info.offset,
            _source: info.source,
        };
        var _undoCid = chartId;
        _tvPushUndo({
            label: 'Remove ' + (info.name || 'indicator'),
            undo: function() {
                _tvAddIndicator(_undoDef, _undoCid);
            },
            redo: function() {
                // Find the indicator by type+period after re-add (seriesIds change)
                var keys = Object.keys(_activeIndicators);
                for (var i = keys.length - 1; i >= 0; i--) {
                    var ai = _activeIndicators[keys[i]];
                    if (ai && ai.chartId === _undoCid && ai.type === _undoDef.key) {
                        _tvRemoveIndicator(keys[i]);
                        break;
                    }
                }
            },
        });
    }

    // Remove requested series and grouped siblings in a single pass.
    var toRemove = [seriesId];
    if (info.group) {
        var gKeys = Object.keys(_activeIndicators);
        for (var gi = 0; gi < gKeys.length; gi++) {
            var gk = gKeys[gi];
            if (gk !== seriesId && _activeIndicators[gk] && _activeIndicators[gk].group === info.group) {
                toRemove.push(gk);
            }
        }
    }

    var removedPanes = {};
    for (var i = 0; i < toRemove.length; i++) {
        var sid = toRemove[i];
        var sinfo = _activeIndicators[sid];
        if (!sinfo) continue;
        var sEntry = window.__PYWRY_TVCHARTS__[sinfo.chartId];
        // Primitive-only indicators (volume profile) don't have an entry in
        // seriesMap — detach the primitive from the host series instead.
        if (_volumeProfilePrimitives[sid]) {
            _tvRemoveVolumeProfilePrimitive(sid);
        }
        if (sEntry && sEntry.seriesMap[sid]) {
            try { sEntry.chart.removeSeries(sEntry.seriesMap[sid]); } catch(e) {}
            delete sEntry.seriesMap[sid];
        }
        // Clean up hidden indicator source series (secondary symbol used for binary indicators)
        if (sinfo.secondarySeriesId && sEntry && sEntry._indicatorSourceSeries && sEntry._indicatorSourceSeries[sinfo.secondarySeriesId]) {
            var secId = sinfo.secondarySeriesId;
            if (sEntry.seriesMap[secId]) {
                try { sEntry.chart.removeSeries(sEntry.seriesMap[secId]); } catch(e) {}
                delete sEntry.seriesMap[secId];
            }
            delete sEntry._indicatorSourceSeries[secId];
            if (sEntry._compareSymbols) delete sEntry._compareSymbols[secId];
            if (sEntry._compareLabels) delete sEntry._compareLabels[secId];
            if (sEntry._compareSymbolInfo) delete sEntry._compareSymbolInfo[secId];
            if (sEntry._seriesRawData) delete sEntry._seriesRawData[secId];
            if (sEntry._seriesCanonicalRawData) delete sEntry._seriesCanonicalRawData[secId];
        }
        if (sinfo.chartId === chartId && sinfo.isSubplot && sinfo.paneIndex > 0) {
            removedPanes[sinfo.paneIndex] = true;
        }
        delete _activeIndicators[sid];
    }

    // Remove empty subplot containers and keep pane indexes in sync.
    if (entry && entry.chart && typeof entry.chart.removePane === 'function') {
        var paneKeys = Object.keys(removedPanes)
            .map(function(v) { return Number(v); })
            .sort(function(a, b) { return b - a; });
        for (var pi = 0; pi < paneKeys.length; pi++) {
            var removedPane = paneKeys[pi];
            var paneStillUsed = false;
            var remaining = Object.keys(_activeIndicators);
            for (var ri = 0; ri < remaining.length; ri++) {
                var ai = _activeIndicators[remaining[ri]];
                if (ai && ai.chartId === chartId && ai.isSubplot && ai.paneIndex === removedPane) {
                    paneStillUsed = true;
                    break;
                }
            }
            if (paneStillUsed) continue;
            var paneRemoved = false;
            try {
                entry.chart.removePane(removedPane);
                paneRemoved = true;
            } catch(e2) {
                try {
                    if (typeof entry.chart.panes === 'function') {
                        var paneObj = entry.chart.panes()[removedPane];
                        if (paneObj) {
                            entry.chart.removePane(paneObj);
                            paneRemoved = true;
                        }
                    }
                } catch(e3) {}
            }
            if (paneRemoved) {
                // Lightweight Charts reindexes panes after removal.
                for (var uj = 0; uj < remaining.length; uj++) {
                    var uid = remaining[uj];
                    var uai = _activeIndicators[uid];
                    if (uai && uai.chartId === chartId && uai.isSubplot && uai.paneIndex > removedPane) {
                        uai.paneIndex -= 1;
                    }
                }
            }
        }
    }

    // Keep next pane index compact after removals.
    if (entry) {
        var maxPane = 0;
        var keys = Object.keys(_activeIndicators);
        for (var k = 0; k < keys.length; k++) {
            var ii = _activeIndicators[keys[k]];
            if (ii && ii.chartId === chartId && ii.isSubplot && ii.paneIndex > maxPane) {
                maxPane = ii.paneIndex;
            }
        }
        entry._nextPane = maxPane + 1;
    }

    // Reset maximize/collapse state — pane layout changed
    if (entry) { entry._paneState = { mode: 'normal', pane: -1 }; delete entry._savedPaneHeights; }

    _tvRebuildIndicatorLegend(chartId);

    // Clean up BB fill canvas if no BB indicators remain on this chart
    if (info.type === 'bollinger-bands') {
        var hasBB = false;
        var remKeys = Object.keys(_activeIndicators);
        for (var bi = 0; bi < remKeys.length; bi++) {
            if (_activeIndicators[remKeys[bi]].chartId === chartId && _activeIndicators[remKeys[bi]].type === 'bollinger-bands') { hasBB = true; break; }
        }
        if (!hasBB) {
            _tvRemoveBBFillPrimitive(chartId);
        } else {
            _tvUpdateBBFill(chartId);
        }
    }

    // Clean up Ichimoku cloud primitive if no Ichimoku groups remain.
    if (info.type === 'ichimoku') {
        var hasIchi = false;
        var iremKeys = Object.keys(_activeIndicators);
        for (var ii = 0; ii < iremKeys.length; ii++) {
            if (_activeIndicators[iremKeys[ii]].chartId === chartId && _activeIndicators[iremKeys[ii]].type === 'ichimoku') { hasIchi = true; break; }
        }
        if (!hasIchi) {
            _tvRemoveIchimokuCloudPrimitive(chartId);
        } else {
            _tvUpdateIchimokuCloud(chartId);
        }
    }
}

// ---------------------------------------------------------------------------
// Indicator legend helpers
// ---------------------------------------------------------------------------

function _tvLegendActionButton(title, iconHtml, onClick) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'tvchart-legend-btn';
    btn.setAttribute('data-tooltip', title);
    btn.setAttribute('aria-label', title);
    btn.innerHTML = iconHtml;
    btn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        if (onClick) onClick(btn, e);
    });
    return btn;
}

function _tvOpenLegendItemMenu(anchorEl, actions) {
    if (!anchorEl || !actions || !actions.length) return;
    var old = document.querySelector('.tvchart-legend-menu');
    if (old && old.parentNode) old.parentNode.removeChild(old);
    var menu = document.createElement('div');
    menu.className = 'tvchart-legend-menu';
    for (var i = 0; i < actions.length; i++) {
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
                if (menu.parentNode) menu.parentNode.removeChild(menu);
                action.run();
            });
            menu.appendChild(item);
        })(actions[i]);
    }
    menu.addEventListener('click', function(e) { e.stopPropagation(); });
    var _oc = _tvAppendOverlay(anchorEl, menu);
    var _cs = _tvContainerSize(_oc);
    var rect = _tvContainerRect(_oc, anchorEl.getBoundingClientRect());
    var menuRect = menu.getBoundingClientRect();
    var left = Math.max(6, Math.min(_cs.width - menuRect.width - 6, rect.right - menuRect.width));
    var top = Math.max(6, Math.min(_cs.height - menuRect.height - 6, rect.bottom + 4));
    menu.style.left = left + 'px';
    menu.style.top = top + 'px';
    setTimeout(function() {
        document.addEventListener('click', function closeMenu() {
            if (menu.parentNode) menu.parentNode.removeChild(menu);
        }, { once: true });
    }, 0);
}

function _tvSetIndicatorVisibility(chartId, seriesId, visible) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.chart) return;
    var target = _activeIndicators[seriesId];
    if (!target) return;
    var keys = Object.keys(_activeIndicators);
    for (var i = 0; i < keys.length; i++) {
        var sid = keys[i];
        var info = _activeIndicators[sid];
        if (!info || info.chartId !== chartId) continue;
        if (target.group && info.group !== target.group) continue;
        if (!target.group && sid !== seriesId) continue;
        var s = entry.seriesMap[sid];
        if (s && typeof s.applyOptions === 'function') {
            try { s.applyOptions({ visible: !!visible }); } catch (e) {}
        }
        // Volume Profile primitives have no real series — toggle the
        // primitive's own hidden flag and request a redraw.
        var vpSlot = _volumeProfilePrimitives[sid];
        if (vpSlot) {
            vpSlot.hidden = !visible;
            if (vpSlot.primitive && vpSlot.primitive.triggerUpdate) vpSlot.primitive.triggerUpdate();
        }
        info.hidden = !visible;
    }
}

function _tvLegendCopyToClipboard(text) {
    var value = String(text || '').trim();
    if (!value) return;
    try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(value);
        }
    } catch (e) {}
}

// ---------------------------------------------------------------------------
// Pane move up/down for subplot indicators
// ---------------------------------------------------------------------------

