function _tvRebuildIndicatorLegend(chartId) {
    var indBox = _tvScopedById(chartId, 'tvchart-legend-indicators');
    if (!indBox) return;
    indBox.innerHTML = '';

    // Clean up previous per-pane legend overlays
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (entry && entry._paneLegendEls) {
        for (var pi in entry._paneLegendEls) {
            if (entry._paneLegendEls[pi] && entry._paneLegendEls[pi].parentNode) {
                entry._paneLegendEls[pi].parentNode.removeChild(entry._paneLegendEls[pi]);
            }
        }
    }
    if (entry) entry._paneLegendEls = {};

    // Compute total pane count for directional button logic
    var totalPanes = 0;
    if (entry && entry.chart && typeof entry.chart.panes === 'function') {
        try { totalPanes = entry.chart.panes().length; } catch (e) {}
    }

    var keys = Object.keys(_activeIndicators);
    var shown = {};
    for (var i = 0; i < keys.length; i++) {
        var sid = keys[i];
        var ai = _activeIndicators[sid];
        if (ai.chartId !== chartId) continue;
        if (ai.group && shown[ai.group]) continue;
        if (ai.group) shown[ai.group] = true;
        (function(seriesId, info) {
            var row = document.createElement('div');
            row.className = 'tvchart-legend-row tvchart-ind-row';
            row.id = 'tvchart-ind-row-' + seriesId;
            row.dataset.hidden = info.hidden ? '1' : '0';
            var dot = document.createElement('span');
            dot.className = 'tvchart-ind-dot';
            // Volume Profile primitives have no line colour — always use
            // the up-volume swatch for the dot so the indicator reads as
            // "Volume Profile" regardless of any stray info.color that a
            // generic settings-apply pass might have written.
            var isVPIndicator = info.type === 'volume-profile-fixed' || info.type === 'volume-profile-visible';
            var dotColor;
            if (isVPIndicator) {
                dotColor = info.upColor || _cssVar('--pywry-tvchart-vp-up');
            } else {
                dotColor = info.color || _cssVar('--pywry-tvchart-text');
            }
            dot.style.background = dotColor;
            row.appendChild(dot);
            var nameSp = document.createElement('span');
            nameSp.className = 'tvchart-ind-name';
            // For VP, keep the name text in the default legend colour —
            // tinting it the low-opacity up-volume blue would render
            // unreadably dim.  Only colour the name when the indicator
            // has a real line colour (SMA/EMA/RSI/etc.).
            nameSp.style.color = isVPIndicator
                ? _cssVar('--pywry-tvchart-text')
                : (info.color || _cssVar('--pywry-tvchart-text'));
            // Extract base name (remove any trailing period in parentheses from the stored name)
            var baseName;
            if (info.group) {
                // Map each grouped indicator's type to its canonical short name.
                if (info.type === 'bollinger-bands') baseName = 'BB';
                else if (info.type === 'macd') baseName = 'MACD';
                else if (info.type === 'stochastic') baseName = 'Stoch';
                else if (info.type === 'aroon') baseName = 'Aroon';
                else if (info.type === 'adx') baseName = 'ADX';
                else if (info.type === 'keltner-channels') baseName = 'KC';
                else if (info.type === 'ichimoku') baseName = 'Ichimoku';
                else baseName = (info.name || '').replace(/\s*\(\d+\)\s*$/, '');
            } else {
                baseName = (info.name || '').replace(/\s*\(\d+\)\s*$/, '');
            }
            // The `inputsInStatusLine` flag toggles the numeric parameter
            // suffix — off → just the short name, on (default) → full
            // TradingView-style string "BB 20 2 0 SMA".
            var showInputs = info.inputsInStatusLine !== false;
            var shortName;
            if (info.group && info.type === 'bollinger-bands') shortName = 'BB';
            else if (info.group && info.type === 'macd') shortName = 'MACD';
            else if (info.group && info.type === 'stochastic') shortName = 'Stoch';
            else if (info.group && info.type === 'aroon') shortName = 'Aroon';
            else if (info.group && info.type === 'adx') shortName = 'ADX';
            else if (info.group && info.type === 'keltner-channels') shortName = 'KC';
            else if (info.group && info.type === 'ichimoku') shortName = 'Ichimoku';
            else if (info.type === 'volume-profile-fixed') shortName = 'VPFR';
            else if (info.type === 'volume-profile-visible') shortName = 'VPVR';
            else shortName = baseName;

            var indLabel;
            if (!showInputs) {
                indLabel = shortName;
            } else if (info.group && info.type === 'bollinger-bands') {
                indLabel = 'BB ' + (info.period || 20) + ' ' + (info.multiplier || 2) + ' ' + (info.offset || 0) + ' ' + (info.maType || 'SMA');
            } else if (info.group && info.type === 'macd') {
                indLabel = 'MACD ' + (info.fast || 12) + ' ' + (info.slow || 26) + ' ' + (info.signal || 9);
            } else if (info.group && info.type === 'stochastic') {
                indLabel = 'Stoch ' + (info.kPeriod || info.period || 14) + ' ' + (info.dPeriod || 3);
            } else if (info.group && info.type === 'aroon') {
                indLabel = 'Aroon ' + (info.period || 14);
            } else if (info.group && info.type === 'adx') {
                indLabel = 'ADX ' + (info.period || 14);
            } else if (info.group && info.type === 'keltner-channels') {
                indLabel = 'KC ' + (info.period || 20) + ' ' + (info.multiplier || 2) + ' ' + (info.maType || 'EMA');
            } else if (info.group && info.type === 'ichimoku') {
                indLabel = 'Ichimoku '
                    + (info.conversionPeriod || info.tenkan || 9) + ' '
                    + (info.basePeriod || info.kijun || 26) + ' '
                    + (info.leadingSpanPeriod || info.senkouB || 52) + ' '
                    + (info.laggingPeriod || 26) + ' '
                    + (info.leadingShiftPeriod || 26);
            } else if (info.type === 'volume-profile-fixed' || info.type === 'volume-profile-visible') {
                var rowsLabel = info.rowsLayout === 'ticks' ? 'Ticks Per Row' : 'Number Of Rows';
                var volLabel = info.volumeMode === 'total'
                    ? 'Total'
                    : (info.volumeMode === 'delta' ? 'Delta' : 'Up/Down');
                var vaPct = Math.round((info.valueAreaPct != null ? info.valueAreaPct : 0.70) * 100);
                indLabel = shortName + ' ' + rowsLabel + ' ' + (info.rowSize || info.period || 24)
                    + ' ' + volLabel + ' ' + vaPct;
            } else {
                indLabel = baseName + (info.period ? ' ' + info.period : '');
            }
            // Binary indicators: show "Indicator source PrimarySymbol / SecondarySymbol"
            if (info.secondarySeriesId) {
                var indEntry = window.__PYWRY_TVCHARTS__[info.chartId];
                var priSym = '';
                var secSym = '';
                if (indEntry) {
                    // Primary symbol from chart title / symbolInfo
                    priSym = (indEntry._resolvedSymbolInfo && indEntry._resolvedSymbolInfo.main && indEntry._resolvedSymbolInfo.main.ticker)
                        || (indEntry.payload && indEntry.payload.title)
                        || '';
                    // Secondary symbol from compare tracking
                    secSym = (indEntry._compareSymbols && indEntry._compareSymbols[info.secondarySeriesId]) || '';
                }
                var srcLabel = info.primarySource || 'close';
                indLabel = baseName + ' ' + srcLabel + ' ' + priSym + ' / ' + secSym;
            }
            nameSp.textContent = indLabel;
            row.appendChild(nameSp);
            // The `valuesInStatusLine` flag toggles the live per-bar
            // readout (crosshair values for normal indicators, running
            // up/down/total for Volume Profile).  When off we skip the
            // span entirely so _tvUpdateIndicatorLegendValues silently
            // no-ops its next lookup.
            var showValues = info.valuesInStatusLine !== false;
            if (showValues) {
                if (info.group) {
                    var gKeys = Object.keys(_activeIndicators);
                    for (var gvi = 0; gvi < gKeys.length; gvi++) {
                        if (_activeIndicators[gKeys[gvi]].group === info.group) {
                            var gValSp = document.createElement('span');
                            gValSp.className = 'tvchart-ind-val';
                            gValSp.id = 'tvchart-ind-val-' + gKeys[gvi];
                            gValSp.style.color = _activeIndicators[gKeys[gvi]].color;
                            row.appendChild(gValSp);
                        }
                    }
                } else {
                    var valSp = document.createElement('span');
                    valSp.className = 'tvchart-ind-val';
                    valSp.id = 'tvchart-ind-val-' + seriesId;
                    // Volume Profile: show running totals (up / down / total).
                    if (info.type === 'volume-profile-fixed' || info.type === 'volume-profile-visible') {
                        var vpSlotForLabel = _volumeProfilePrimitives[seriesId];
                        if (vpSlotForLabel) {
                            var t = _tvVolumeProfileTotals(vpSlotForLabel.vpData);
                            valSp.textContent = _tvFormatVolume(t.up) + '  '
                                + _tvFormatVolume(t.down) + '  '
                                + _tvFormatVolume(t.total);
                        }
                    }
                    row.appendChild(valSp);
                }
            }
            var ctrl = document.createElement('span');
            ctrl.className = 'tvchart-legend-row-actions tvchart-ind-ctrl';
            var upArrowSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="display:block"><path d="M8 13V3"/><path d="M3 7l5-5 5 5"/></svg>';
            var downArrowSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="display:block"><path d="M8 3v10"/><path d="M3 9l5 5 5-5"/></svg>';
            var maximizeSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="display:block"><rect x="2.5" y="2.5" width="11" height="11" rx="1.5"/></svg>';
            var hideSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" style="display:block"><path d="M1.8 8s2.2-3.8 6.2-3.8S14.2 8 14.2 8s-2.2 3.8-6.2 3.8S1.8 8 1.8 8z"/><circle cx="8" cy="8" r="1.9"/></svg>';
            var showSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" style="display:block"><path d="M1.8 8s2.2-3.8 6.2-3.8S14.2 8 14.2 8s-2.2 3.8-6.2 3.8S1.8 8 1.8 8z"/><circle cx="8" cy="8" r="1.9"/><line x1="3" y1="13" x2="13" y2="3" stroke-width="1.6"/></svg>';
            var settingsSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor" style="display:block"><path d="M8 10.2a2.2 2.2 0 100-4.4 2.2 2.2 0 000 4.4zm4.8-2.7a.5.5 0 01.3-.46l.46-.27a.5.5 0 00.18-.68l-.54-.94a.5.5 0 00-.68-.18l-.46.27a.5.5 0 01-.53-.05 4.4 4.4 0 00-.55-.32.5.5 0 01-.3-.45V3.9A.5.5 0 0010.19 3.5H9.12a.5.5 0 00-.5.46v.51a.5.5 0 01-.3.45 4.4 4.4 0 00-.55.32.5.5 0 01-.53.05l-.46-.27a.5.5 0 00-.68.18l-.54.94a.5.5 0 00.18.68l.46.27a.5.5 0 01.3.46v.02a.5.5 0 01-.3.46l-.46.27a.5.5 0 00-.18.68l.54.94a.5.5 0 00.68.18l.46-.27a.5.5 0 01.53.05c.17.12.35.22.55.32a.5.5 0 01.3.45v.51A.5.5 0 0010.19 12.5H9.12a.5.5 0 01-.5-.46v-.51a.5.5 0 00-.3-.45 4.4 4.4 0 01-.55-.32.5.5 0 00-.53.05l-.46.27a.5.5 0 01-.68-.18l-.54-.94a.5.5 0 01.18-.68l.46-.27a.5.5 0 00.3-.46v-.02z"/></svg>';
            var removeSvg = '<svg viewBox="0 0 16 16" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" style="display:block"><line x1="4" y1="4" x2="12" y2="12"/><line x1="12" y1="4" x2="4" y2="12"/></svg>';
            var menuSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor" style="display:block"><circle cx="3.5" cy="8" r="1.2"/><circle cx="8" cy="8" r="1.2"/><circle cx="12.5" cy="8" r="1.2"/></svg>';
            var copySvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" style="display:block"><rect x="5.2" y="3.6" width="7.2" height="8.6" rx="1.4"/><path d="M3.6 10.4V5.1c0-.9.7-1.6 1.6-1.6h4.4"/></svg>';

            // Pane move buttons for subplot indicators
            if (info.isSubplot) {
                var canMoveUp = info.paneIndex > 0;
                var canMoveDown = totalPanes > 0 && info.paneIndex < totalPanes - 1;
                if (canMoveUp) {
                    ctrl.appendChild(_tvLegendActionButton('Move pane up', upArrowSvg, function() {
                        _tvSwapIndicatorPane(chartId, seriesId, -1);
                    }));
                }
                if (canMoveDown) {
                    ctrl.appendChild(_tvLegendActionButton('Move pane down', downArrowSvg, function() {
                        _tvSwapIndicatorPane(chartId, seriesId, 1);
                    }));
                }
                // Maximize pane button
                var paneBtn = _tvLegendActionButton('Maximize pane', maximizeSvg, function() {
                    var pState = _tvGetPaneState(chartId);
                    var isThisPane = pState.pane === info.paneIndex;
                    if (pState.mode === 'maximized' && isThisPane) {
                        _tvRestorePanes(chartId);
                    } else {
                        _tvMaximizePane(chartId, info.paneIndex);
                    }
                });
                paneBtn.id = 'tvchart-pane-ctrl-' + seriesId;
                ctrl.appendChild(paneBtn);
                // Collapse pane button (minimize icon — horizontal line)
                var collapseSvg = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="display:block"><line x1="3" y1="8" x2="13" y2="8"/></svg>';
                var collapseBtn = _tvLegendActionButton('Collapse pane', collapseSvg, function() {
                    var pState = _tvGetPaneState(chartId);
                    var isThisPane = pState.pane === info.paneIndex;
                    if (pState.mode === 'collapsed' && isThisPane) {
                        _tvRestorePanes(chartId);
                    } else {
                        _tvCollapsePane(chartId, info.paneIndex);
                    }
                });
                collapseBtn.id = 'tvchart-pane-collapse-' + seriesId;
                ctrl.appendChild(collapseBtn);
            }
            var eyeBtn = _tvLegendActionButton(info.hidden ? 'Show' : 'Hide', info.hidden ? showSvg : hideSvg, function(btn) {
                var hidden = !info.hidden;
                _tvSetIndicatorVisibility(chartId, seriesId, !hidden);
                row.dataset.hidden = hidden ? '1' : '0';
                btn.setAttribute('data-tooltip', hidden ? 'Show' : 'Hide');
                btn.setAttribute('aria-label', hidden ? 'Show' : 'Hide');
                btn.innerHTML = hidden ? showSvg : hideSvg;
            });
            eyeBtn.id = 'tvchart-eye-' + seriesId;
            ctrl.appendChild(eyeBtn);
            ctrl.appendChild(_tvLegendActionButton('Settings', settingsSvg, function() {
                try {
                    _tvShowIndicatorSettings(seriesId);
                } catch (err) {
                    console.error('[pywry:tvchart] Settings dialog failed for', seriesId, err);
                }
            }));
            ctrl.appendChild(_tvLegendActionButton('Remove', removeSvg, function() {
                _tvRemoveIndicator(seriesId);
            }));
            ctrl.appendChild(_tvLegendActionButton('More', menuSvg, function(btn) {
                var fullName = (info.name || '').trim();
                var groupName = info.group ? 'Indicator group' : 'Single indicator';
                _tvOpenLegendItemMenu(btn, [
                    {
                        label: info.hidden ? 'Show' : 'Hide',
                        icon: info.hidden ? showSvg : hideSvg,
                        run: function() {
                            var hidden = !info.hidden;
                            _tvSetIndicatorVisibility(chartId, seriesId, !hidden);
                            row.dataset.hidden = hidden ? '1' : '0';
                            var eb = document.getElementById('tvchart-eye-' + seriesId);
                            if (eb) {
                                eb.setAttribute('data-tooltip', hidden ? 'Show' : 'Hide');
                                eb.setAttribute('aria-label', hidden ? 'Show' : 'Hide');
                                eb.innerHTML = hidden ? showSvg : hideSvg;
                            }
                        },
                    },
                    {
                        label: 'Settings',
                        icon: settingsSvg,
                        run: function() { _tvShowIndicatorSettings(seriesId); },
                    },
                    {
                        label: 'Remove',
                        icon: removeSvg,
                        run: function() { _tvRemoveIndicator(seriesId); },
                    },
                    { separator: true },
                    {
                        label: 'Copy Name',
                        icon: copySvg,
                        meta: fullName || groupName,
                        disabled: !fullName,
                        tooltip: fullName || 'Indicator name unavailable',
                        run: function() { _tvLegendCopyToClipboard(fullName); },
                    },
                    {
                        label: 'Reset Visibility',
                        icon: hideSvg,
                        meta: groupName,
                        run: function() {
                            _tvSetIndicatorVisibility(chartId, seriesId, true);
                            row.dataset.hidden = '0';
                            var eb = document.getElementById('tvchart-eye-' + seriesId);
                            if (eb) {
                                eb.setAttribute('data-tooltip', 'Hide');
                                eb.setAttribute('aria-label', 'Hide');
                                eb.innerHTML = hideSvg;
                            }
                        },
                    },
                ]);
            }));
            row.appendChild(ctrl);

            // Route subplot indicators to per-pane legend overlays.
            // Always append to indBox first; a deferred pass will relocate
            // subplot rows into their pane overlays once the DOM is laid out.
            indBox.appendChild(row);
        })(sid, ai);
    }

    // Deferred: move subplot indicator rows into per-pane overlays once
    // LWC has finished laying out pane DOM elements (getBoundingClientRect
    // returns zeros when called synchronously after addSeries).
    if (entry && entry.chart) {
        requestAnimationFrame(function() {
            _tvRelocateSubplotLegends(chartId);
            _tvUpdatePaneControlButtons(chartId);
        });
    }
}

/**
 * Move subplot indicator legend rows from the main indBox into per-pane
 * overlay containers.  Called after a rAF so LWC pane DOM is laid out.
 */
function _tvRelocateSubplotLegends(chartId) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.chart) return;
    var mainPane = _tvFindMainChartPane(entry);
    var keys = Object.keys(_activeIndicators);
    var shown = {};
    for (var i = 0; i < keys.length; i++) {
        var sid = keys[i];
        var ai = _activeIndicators[sid];
        if (ai.chartId !== chartId) continue;
        if (ai.group && shown[ai.group]) continue;
        if (ai.group) shown[ai.group] = true;
        // Keep non-subplot and indicators in the main chart pane in indBox
        if (!ai.isSubplot || ai.paneIndex === mainPane) continue;
        var row = document.getElementById('tvchart-ind-row-' + sid);
        if (!row) continue;
        var paneEl = _tvGetPaneLegendContainer(entry, ai.paneIndex);
        if (paneEl) {
            paneEl.appendChild(row); // moves the node out of indBox
        }
    }
}

function _tvUpdateIndicatorLegendValues(chartId, param) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry) return;
    // Reposition pane legends (handles pane divider drag)
    _tvRepositionPaneLegends(chartId);
    var keys = Object.keys(_activeIndicators);
    for (var i = 0; i < keys.length; i++) {
        var sid = keys[i];
        var info = _activeIndicators[sid];
        if (info.chartId !== chartId) continue;
        var valSp = _tvScopedById(chartId, 'tvchart-ind-val-' + sid);
        if (!valSp) continue;
        var series = entry.seriesMap[sid];
        if (!series) continue;
        var d = param && param.seriesData ? param.seriesData.get(series) : null;
        if (d && d.value !== undefined) {
            valSp.textContent = '\u00a0' + Number(d.value).toFixed(2);
        }
    }
}

