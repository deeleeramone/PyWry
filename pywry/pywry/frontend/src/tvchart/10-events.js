// ---------------------------------------------------------------------------
// Event handlers from Python (pywry.dispatch)
// ---------------------------------------------------------------------------

(function() {
    function onReady(bridge) {
        // Accept explicit bridge parameter (per-widget in notebook mode).
        // Falls back to window.pywry for native-window mode.
        bridge = bridge || window.pywry;
        if (!bridge || typeof bridge.on !== 'function') {
            setTimeout(function() { onReady(bridge); }, 50);
            return;
        }

        // Chart ID owned by THIS bridge.  In notebook mode each widget sets
        // bridge._chartId to its unique chart identifier.  Used as fallback
        // instead of 'main' (which is a SERIES id, not a chart id).
        var _cid = bridge._chartId || null;

        // In native mode, ``bridge._chartId`` is undefined at onReady
        // time because the chart is created later via a direct call
        // to ``PYWRY_TVCHART_CREATE`` (bypassing the ``tvchart:create``
        // event).  Wire a property accessor so that when
        // ``PYWRY_TVCHART_CREATE`` later sets ``bridge._chartId``, the
        // closure variable ``_cid`` updates automatically.
        if (!_cid) {
            Object.defineProperty(bridge, '_chartId', {
                get: function() { return _cid; },
                set: function(v) { _cid = v; },
                configurable: true,
            });
        }

        // Resolve a chart id from event data, falling back to the
        // bridge's owned ``_cid`` and finally to whatever chart is
        // registered on ``__PYWRY_TVCHARTS__``.  Single-widget native-
        // window mode doesn't always have ``_cid`` populated in time
        // (e.g. an event fires before the create handler runs), so the
        // registry fallback keeps handlers that operate on the live
        // chart (visibility / lock / state) from silently no-op'ing.
        function _resolveCid(data) {
            if (data && data.chartId) return data.chartId;
            if (_cid) return _cid;
            var reg = window.__PYWRY_TVCHARTS__;
            if (reg) {
                var keys = Object.keys(reg);
                if (keys.length) return keys[0];
            }
            return null;
        }

        // Python → JS: create chart
        bridge.on('tvchart:create', function(data) {
            var container = data.containerId
                ? document.getElementById(data.containerId)
                : document.querySelector('.pywry-tvchart-container');
            if (!container) {
                console.error('[pywry:tvchart] container not found:', data.containerId || '.pywry-tvchart-container');
                return;
            }
            var chartId = data.chartId || _cid;
            // In native mode bridge._chartId is null, so capture the first
            // chartId from the create payload for subsequent handlers.
            if (!_cid && chartId) _cid = chartId;
            window.PYWRY_TVCHART_CREATE(chartId, container, data);
        });

        // Python → JS: update data
        bridge.on('tvchart:data-response', function(data) {
            var chartId = data.chartId || _cid;
            var resolved = _tvResolveChartEntry(chartId);
            var entry = resolved ? resolved.entry : null;
            if (!entry || !entry.chart) return;
            var seriesId = data.seriesId || 'main';

            // When the main series receives new bars with a different
            // interval OR a different symbol, destroy and fully recreate
            // the chart so candles + volume stay in perfect 1-to-1 sync
            // and no stale compare / overlay / aux series (e.g. HLC fill
            // layers from a prior chart type) linger on the canvas.
            // Partial updates replace ``main``'s data but can't scrub
            // other series out of the chart object.
            //
            // The rebuild window briefly makes the chart entry
            // unavailable; ``tvchart:request-state`` answers
            // ``{chartId, error: "not found"}`` during that gap.  The
            // Python-side ``_fetch_tvchart_state`` helper treats any
            // response with an ``error`` field as ``None`` so the
            // mutation-confirmation poll keeps retrying until the new
            // chart is back up with real state.  Don't try to avoid
            // the rebuild — the ghost-series and volume-alignment bugs
            // that destroy-recreate cures are worse than a ~200ms poll
            // retry window.
            if (seriesId === 'main' && (data.interval || data.symbol)) {
                var hasBars = data.bars && data.bars.length > 0;
                var isDatafeed = entry.payload && entry.payload.useDatafeed;
                var currentInterval = (entry.payload && entry.payload.interval) || '';
                var currentMainSymbol = '';
                if (entry.payload && entry.payload.series && entry.payload.series[0]) {
                    currentMainSymbol = String(entry.payload.series[0].symbol || '').toUpperCase();
                }
                var incomingSymbol = data.symbol ? String(data.symbol).toUpperCase() : '';
                var intervalChanged = data.interval && data.interval !== currentInterval;
                var symbolChanged = incomingSymbol && currentMainSymbol && incomingSymbol !== currentMainSymbol;
                if ((intervalChanged || symbolChanged) && (hasBars || isDatafeed)) {
                    var container = entry.container;
                    var oldPayload = entry.payload || {};
                    var savedDisplayStyle = entry._chartDisplayStyle || null;

                    // Capture the visible *time* range before destroy so we
                    // can restore the user's zoom on the new chart.  Time-
                    // based (not logical/bar-index) so it works across
                    // interval changes where bar counts differ.
                    var savedVisibleTimeRange = null;
                    try {
                        savedVisibleTimeRange = entry.chart.timeScale().getVisibleRange();
                    } catch (e) {}

                    // Save compare symbols and indicators before destroy
                    var savedCompareSymbols = entry._compareSymbols ? _tvMerge(entry._compareSymbols, {}) : null;
                    var savedCompareLabels = entry._compareLabels ? _tvMerge(entry._compareLabels, {}) : null;
                    var savedCompareSymbolInfo = entry._compareSymbolInfo ? _tvMerge(entry._compareSymbolInfo, {}) : null;
                    var savedCompareModes = {};
                    var savedIndicators = [];
                    var cid = resolved ? resolved.chartId : chartId;

                    // Capture active indicators for this chart
                    var indKeys = Object.keys(_activeIndicators);
                    for (var ik = 0; ik < indKeys.length; ik++) {
                        var indInfo = _activeIndicators[indKeys[ik]];
                        if (indInfo && indInfo.chartId === cid) {
                            savedIndicators.push(_tvMerge(indInfo, {}));
                        }
                    }

                    // Merge new bars into the rebuilt payload.  Interval and
                    // symbol may each be unchanged (symbol-only change keeps
                    // the old interval; interval-only change keeps the old
                    // symbol) — fall back to the current value in either case.
                    var effectiveInterval = data.interval || currentInterval;
                    var effectiveSymbol = incomingSymbol || currentMainSymbol;
                    var newPayload = _tvMerge(oldPayload, {});
                    newPayload.interval = effectiveInterval;

                    if (newPayload.useDatafeed) {
                        // Datafeed mode: pre-fill bars from provider.get_bars() so
                        // _tvInitDatafeedMode can skip the redundant getBars call.
                        if (newPayload.series && Array.isArray(newPayload.series) && newPayload.series[0]) {
                            newPayload.series[0].resolution = effectiveInterval;
                            if (effectiveSymbol) newPayload.series[0].symbol = effectiveSymbol;
                            newPayload.series[0].bars = data.bars || [];
                            newPayload.series[0].volume = [];
                        }
                    } else {
                        if (newPayload.series && Array.isArray(newPayload.series) && newPayload.series[0]) {
                            if (effectiveSymbol) newPayload.series[0].symbol = effectiveSymbol;
                            newPayload.series[0].bars = data.bars;
                            newPayload.series[0].volume = [];
                        } else {
                            newPayload.bars = data.bars;
                            newPayload.volume = [];
                        }
                    }
                    if (effectiveSymbol) newPayload.title = effectiveSymbol;

                    // Symbol change wipes prior compares/indicators — they
                    // belong to the old ticker, not the new one.  Interval-
                    // only change preserves them (handled by the saved vars
                    // below).
                    if (symbolChanged) {
                        savedCompareSymbols = null;
                        savedCompareLabels = null;
                        savedCompareSymbolInfo = null;
                        savedIndicators = [];
                    }
                    // Destroy then recreate
                    window.PYWRY_TVCHART_DESTROY(cid);
                    container.innerHTML = '';
                    window.PYWRY_TVCHART_CREATE(cid, container, newPayload);

                    // Hand the pre-destroy zoom off to the new chart so its
                    // ``applyDefault`` (setTimeout 150ms in lifecycle) honours
                    // the user's prior zoom instead of falling through to
                    // fitContent.  Clamp to the new data bounds so a symbol
                    // with shorter history doesn't end up pointing off the
                    // end of its bars.
                    (function() {
                        var reEntry = window.__PYWRY_TVCHARTS__[cid];
                        if (!reEntry || !savedVisibleTimeRange) return;
                        var newBars = Array.isArray(data.bars) ? data.bars : [];
                        if (!newBars.length) return;
                        var firstTime = newBars[0].time;
                        var lastTime = newBars[newBars.length - 1].time;
                        var from = savedVisibleTimeRange.from;
                        var to = savedVisibleTimeRange.to;
                        if (from == null || to == null || firstTime == null || lastTime == null) return;
                        if (to <= firstTime || from >= lastTime) {
                            // Saved range is entirely outside the new data
                            // (e.g. viewing old AAPL history on a short-
                            // history ticker).  Re-anchor to the end with
                            // the same width.
                            var width = to - from;
                            if (!(width > 0)) return;
                            to = lastTime;
                            from = Math.max(firstTime, lastTime - width);
                        } else {
                            from = Math.max(from, firstTime);
                            to = Math.min(to, lastTime);
                        }
                        if (!(from < to)) return;
                        reEntry._preservedVisibleTimeRange = { from: from, to: to };
                    })();

                    _tvSetIntervalUi(cid, effectiveInterval);

                    // Track every piece of deferred post-CREATE work so
                    // ``tvchart:data-settled`` fires ONLY when the chart is
                    // actually stable.  Python tools that chain mutation
                    // calls (symbol → interval → zoom) use this signal to
                    // sequence their calls — if it fires early, the next
                    // tool races the still-in-flight rebuild and its
                    // effect gets clobbered (e.g. a zoom reverts when the
                    // late-firing applyDefault restores the pre-destroy
                    // range).
                    //
                    // Work to wait on, in order of scheduled time:
                    //   1. ``entry.whenMainSeriesReady`` — main series
                    //      attached (sync in static-bar mode, async via
                    //      resolveSymbol in datafeed mode).
                    //   2. chart-type-change re-apply — chains off (1).
                    //   3. indicator re-add — setTimeout(100).
                    //   4. lifecycle applyDefault — setTimeout(150), owns
                    //      ``_preservedVisibleTimeRange``.
                    var _pending = 0;
                    var _settledFired = false;
                    var _fireSettled = function() {
                        if (_pending > 0 || _settledFired) return;
                        _settledFired = true;
                        var finalState = _tvExportState(cid);
                        bridge.emit('tvchart:data-settled', finalState || {
                            chartId: cid, error: 'not found',
                        });
                    };
                    var _track = function() {
                        _pending++;
                        var settled = false;
                        return function() {
                            if (settled) return;
                            settled = true;
                            _pending--;
                            _fireSettled();
                        };
                    };

                    // Wait for lifecycle applyDefault to consume the
                    // preserved range.  Its setTimeout is 150ms; add a
                    // 30ms safety buffer.
                    var _applyDefaultDone = _track();
                    setTimeout(_applyDefaultDone, 180);

                    // Re-apply chart display style once the new main
                    // series is attached.  Event-driven via
                    // ``whenMainSeriesReady`` — no polling.
                    if (savedDisplayStyle) {
                        var _styleDone = _track();
                        var _reEntryForStyle = window.__PYWRY_TVCHARTS__[cid];
                        if (_reEntryForStyle && typeof _reEntryForStyle.whenMainSeriesReady === 'function') {
                            _reEntryForStyle.whenMainSeriesReady(function() {
                                // Seed ``_chartDisplayStyle`` before the
                                // emit so legend/settings pick it up
                                // during the switch.
                                _reEntryForStyle._chartDisplayStyle = savedDisplayStyle;
                                bridge.emit('tvchart:chart-type-change', {
                                    value: savedDisplayStyle,
                                    chartId: cid,
                                });
                                _styleDone();
                            });
                        } else {
                            // Entry gone before we could register — nothing
                            // to do, but still settle the tracker.
                            _styleDone();
                        }
                    }

                    // Re-request compare symbols at the new interval
                    if (savedCompareSymbols) {
                        var newEntry = window.__PYWRY_TVCHARTS__[cid];
                        if (newEntry) {
                            newEntry._pendingCompareModes = savedCompareModes;
                        }
                        var cmpIds = Object.keys(savedCompareSymbols);
                        for (var ci = 0; ci < cmpIds.length; ci++) {
                            var cmpSid = cmpIds[ci];
                            var cmpSym = savedCompareSymbols[cmpSid];
                            if (!cmpSym) continue;
                            bridge.emit('tvchart:data-request', {
                                chartId: cid,
                                symbol: cmpSym,
                                symbolInfo: savedCompareSymbolInfo ? savedCompareSymbolInfo[cmpSid] : null,
                                seriesId: cmpSid,
                                interval: effectiveInterval,
                                resolution: effectiveInterval,
                                periodParams: {
                                    from: 0,
                                    to: Math.floor(Date.now() / 1000),
                                    countBack: 300,
                                    firstDataRequest: true,
                                },
                            });
                        }
                    }

                    // Re-add indicators after a short delay to allow main
                    // series data to be set (indicators compute from raw
                    // bar data).  Tracked so data-settled waits for it.
                    if (savedIndicators.length > 0) {
                        var _indDone = _track();
                        setTimeout(function() {
                            var reEntry = window.__PYWRY_TVCHARTS__[cid];
                            if (reEntry) {
                                for (var si = 0; si < savedIndicators.length; si++) {
                                    var ind = savedIndicators[si];
                                    _tvAddIndicator({
                                        name: ind.name,
                                        key: ind.type,
                                        defaultPeriod: ind.period,
                                        _color: ind.color,
                                        _source: ind.source,
                                        _method: ind.method,
                                        _multiplier: ind.multiplier,
                                        requiresSecondary: !!ind.secondarySeriesId,
                                    }, cid);
                                }
                            }
                            _indDone();
                        }, 100);
                    }

                    _tvRefreshLegendTitle(cid);
                    _tvEmitLegendRefresh(cid);
                    _tvRenderHoverLegend(cid, null);

                    // All deferred tasks are registered — if none were
                    // queued this call settles immediately.
                    _fireSettled();
                    return;
                }
            }

            if (!entry.seriesMap[seriesId]) {
                var sType = data.seriesType || 'Line';
                var sOpts = _tvBuildSeriesOptions(data.seriesOptions || {}, sType, entry.theme);
                var compareMode = data.compareMode || (entry._pendingCompareModes && entry._pendingCompareModes[seriesId]) || 'new_price_scale';
                var paneIndex;
                if (compareMode === 'same_percent') {
                    sOpts.priceScaleId = _tvResolveScalePlacement(entry);
                    try { entry.chart.priceScale(sOpts.priceScaleId).applyOptions({ mode: 2, autoScale: true }); } catch (e) {}
                } else if (compareMode === 'new_pane') {
                    paneIndex = _tvReserveComparePane(entry, seriesId);
                    sOpts.priceScaleId = seriesId;
                    _tvRegisterCustomPriceScaleId(entry, sOpts.priceScaleId);
                } else {
                    sOpts.priceScaleId = seriesId;
                    _tvRegisterCustomPriceScaleId(entry, sOpts.priceScaleId);
                }
                var series = _tvAddSeriesCompat(entry.chart, sType, sOpts, paneIndex);
                entry.seriesMap[seriesId] = series;
                if (!entry._legendSeriesColors) entry._legendSeriesColors = {};
                entry._legendSeriesColors[seriesId] = (
                    sOpts.color ||
                    sOpts.lineColor ||
                    sOpts.upColor ||
                    sOpts.borderUpColor ||
                    '#4c87ff'
                );
                if (entry._pendingCompareModes && entry._pendingCompareModes[seriesId]) {
                    delete entry._pendingCompareModes[seriesId];
                }
                if (data.symbol && seriesId !== 'main' && !_activeIndicators[seriesId]) {
                    if (!entry._compareSymbols) entry._compareSymbols = {};
                    entry._compareSymbols[seriesId] = String(data.symbol).toUpperCase();
                    if (!entry._compareLabels) entry._compareLabels = {};
                    entry._compareLabels[seriesId] = _tvDisplayLabelFromSymbolInfo(data.symbolInfo || null, data.symbol);
                    if (data.symbolInfo) {
                        if (!entry._compareSymbolInfo) entry._compareSymbolInfo = {};
                        entry._compareSymbolInfo[seriesId] = data.symbolInfo;
                    }
                }
            }
            if (data.seriesOptions) {
                if (!entry._legendSeriesColors) entry._legendSeriesColors = {};
                var legendColor = data.seriesOptions.color || data.seriesOptions.lineColor || data.seriesOptions.upColor || data.seriesOptions.borderUpColor;
                if (legendColor) entry._legendSeriesColors[seriesId] = legendColor;
            }
            // Binary indicator flow: save visible range before update so we
            // can restore it after adding the indicator subplot.
            var _savedRange = null;
            var _isIndicatorFlow = !!(entry._pendingBinaryIndicator && seriesId !== 'main');
            if (_isIndicatorFlow) {
                try { _savedRange = entry.chart.timeScale().getVisibleLogicalRange(); } catch (e) {}
            }

            // Symbol change on main series (same interval): preserve the
            // WIDTH of the previous zoom but re-anchor the right edge to
            // the new symbol's last bar.  Restoring the old logical range
            // verbatim puts the viewport off the end of shorter-history
            // symbols (one lonely candle stranded on the left).
            var _isSymbolChange = (seriesId === 'main' && data.interval &&
                data.interval === ((entry.payload && entry.payload.interval) || ''));
            var _savedWidth = null;
            if (_isSymbolChange) {
                try {
                    var _pre = entry.chart.timeScale().getVisibleLogicalRange();
                    if (_pre) _savedWidth = Math.max(1, _pre.to - _pre.from);
                } catch (e) {}
            }

            // Compare / overlay add on a non-main series should preserve the
            // user's current zoom — the default ``fitContent: true`` in the
            // data-response payload would otherwise reset the view every
            // time a compare or overlay arrives.  The binary-indicator
            // flow handles its own range save below, so skip this path
            // when that's in effect.
            var _isCompareAdd = !_isIndicatorFlow && !_isSymbolChange && seriesId !== 'main';
            var _savedCompareTimeRange = null;
            if (_isCompareAdd) {
                try { _savedCompareTimeRange = entry.chart.timeScale().getVisibleRange(); } catch (e) {}
            }

            var _suppressFit = _isIndicatorFlow || _isSymbolChange || _isCompareAdd;
            window.PYWRY_TVCHART_UPDATE(chartId, _suppressFit ? _tvMerge(data, { fitContent: false }) : data);

            if (_isCompareAdd && _savedCompareTimeRange
                && _savedCompareTimeRange.from != null && _savedCompareTimeRange.to != null) {
                try {
                    entry.chart.timeScale().setVisibleRange({
                        from: _savedCompareTimeRange.from,
                        to: _savedCompareTimeRange.to,
                    });
                } catch (e) {}
            }

            if (_isSymbolChange) {
                var _bars = Array.isArray(data.bars) ? data.bars : [];
                if (_bars.length > 0) {
                    var _last = _bars[_bars.length - 1];
                    var _width = _savedWidth && _savedWidth < _bars.length ? _savedWidth : _bars.length;
                    var _firstIdx = Math.max(0, _bars.length - Math.ceil(_width));
                    var _first = _bars[_firstIdx];
                    if (_first && _last && _first.time != null && _last.time != null) {
                        try {
                            entry.chart.timeScale().setVisibleRange({
                                from: _first.time,
                                to: _last.time,
                            });
                        } catch (e) {
                            // setVisibleRange can reject if the range is
                            // degenerate — fall back to scrolling to the
                            // real-time edge so the last bar is at least
                            // on-screen.
                            try { entry.chart.timeScale().scrollToRealTime(); } catch (e2) {}
                        }
                    } else {
                        try { entry.chart.timeScale().scrollToRealTime(); } catch (e) {}
                    }
                } else {
                    try { entry.chart.timeScale().fitContent(); } catch (e) {}
                }
            }

            // Binary indicator flow: hide the raw compare series and compute
            // the indicator now that secondary data is available.
            if (_isIndicatorFlow) {
                var pendingDef = entry._pendingBinaryIndicator;
                delete entry._pendingBinaryIndicator;
                // Hide the compare series — only the computed indicator subplot should be visible
                var compareSeries = entry.seriesMap[seriesId];
                if (compareSeries) {
                    try { compareSeries.applyOptions({ visible: false, lastValueVisible: false, priceLineVisible: false }); } catch (e) {}
                    // Also hide the price scale so no extra axis appears on the main pane
                    try {
                        var scaleId = seriesId;
                        entry.chart.priceScale(scaleId).applyOptions({ visible: false });
                    } catch (e) {}
                }
                // Mark as indicator source so legend/compare panel skip it
                if (!entry._indicatorSourceSeries) entry._indicatorSourceSeries = {};
                entry._indicatorSourceSeries[seriesId] = true;
                // Now add the indicator — secondary series is available
                _tvAddIndicator(pendingDef, resolved ? resolved.chartId : chartId);
                // If this was a symbol-change edit, remove the old indicator
                if (entry._pendingReplaceIndicator) {
                    _tvRemoveIndicator(entry._pendingReplaceIndicator);
                    delete entry._pendingReplaceIndicator;
                }
                // Restore the visible range so the chart doesn't jump
                if (_savedRange) {
                    try { entry.chart.timeScale().setVisibleLogicalRange(_savedRange); } catch (e) {}
                }
            }

            _tvRefreshLegendTitle(resolved ? resolved.chartId : chartId);
            _tvEmitLegendRefresh(resolved ? resolved.chartId : chartId);
            _tvRenderHoverLegend(resolved ? resolved.chartId : chartId, null);

            // Signal that this data-response has been fully processed
            // (compare/overlay add, in-place symbol swap, etc.) so the
            // Python mutation handler waiting on this round-trip can
            // return deterministic confirmed state instead of polling.
            var _settledCid = resolved ? resolved.chartId : chartId;
            var _settledState = _tvExportState(_settledCid);
            bridge.emit('tvchart:data-settled', _settledState || {
                chartId: _settledCid, error: 'not found',
            });
        });

        bridge.on('tvchart:update', function(data) {
            var chartId = data.chartId || _cid;
            window.PYWRY_TVCHART_UPDATE(chartId, data);
        });

        // Python → JS: stream single bar
        bridge.on('tvchart:stream', function(data) {
            var chartId = data.chartId || _cid;
            window.PYWRY_TVCHART_STREAM(chartId, data);
        });

        // Python → JS: destroy chart
        bridge.on('tvchart:destroy', function(data) {
            var chartId = data.chartId || _cid;
            window.PYWRY_TVCHART_DESTROY(chartId);
        });

        // Python → JS: apply chart options
        bridge.on('tvchart:apply-options', function(data) {
            var resolved = _tvResolveChartEntry(data.chartId || _cid);
            var entry = resolved ? resolved.entry : null;
            if (!entry || !entry.chart) return;
            if (data.chartOptions) {
                entry.chart.applyOptions(data.chartOptions);
            }
            if (data.seriesOptions) {
                var s = entry.seriesMap[data.seriesId || 'main'];
                if (s) s.applyOptions(data.seriesOptions);
            }
        });

        // Python → JS: add an overlay/indicator series
        bridge.on('tvchart:add-series', function(data) {
            var resolved = _tvResolveChartEntry(data.chartId || _cid);
            var entry = resolved ? resolved.entry : null;
            if (!entry || !entry.chart) return;
            var sType = data.seriesType || 'Line';
            var constructorName = SERIES_TYPES[sType] || 'LineSeries';
            var sOpts = _tvBuildSeriesOptions(data.seriesOptions || {}, sType, entry.theme);
            var seriesId = data.seriesId || ('overlay-' + Object.keys(entry.seriesMap).length);
            var compareMode = data.compareMode || (entry._pendingCompareModes && entry._pendingCompareModes[seriesId]) || 'new_price_scale';
            var paneIndex;
            if (compareMode === 'same_percent') {
                sOpts.priceScaleId = _tvResolveScalePlacement(entry);
                try {
                    entry.chart.priceScale(sOpts.priceScaleId).applyOptions({
                        mode: 2,
                        autoScale: true,
                    });
                } catch (e) {}
            } else if (compareMode === 'new_pane') {
                paneIndex = _tvReserveComparePane(entry, seriesId);
                sOpts.priceScaleId = seriesId;
                _tvRegisterCustomPriceScaleId(entry, sOpts.priceScaleId);
            } else {
                sOpts.priceScaleId = seriesId;
                _tvRegisterCustomPriceScaleId(entry, sOpts.priceScaleId);
            }
            var series = _tvAddSeriesCompat(entry.chart, sType, sOpts, paneIndex);
            var sourceBars = Array.isArray(data.bars) ? data.bars : [];
            var bars = _tvNormalizeBarsForSeriesType(sourceBars, sType);
            series.setData(bars);
            entry.seriesMap[seriesId] = series;
            entry._seriesRawData[seriesId] = bars;
            if (!entry._seriesCanonicalRawData) entry._seriesCanonicalRawData = {};
            if (_tvLooksLikeOhlcBars(sourceBars)) {
                entry._seriesCanonicalRawData[seriesId] = sourceBars;
            }
            if (!entry._legendSeriesColors) entry._legendSeriesColors = {};
            entry._legendSeriesColors[seriesId] = (
                sOpts.color ||
                sOpts.lineColor ||
                sOpts.upColor ||
                sOpts.borderUpColor ||
                '#4c87ff'
            );
            if (entry._pendingCompareModes && entry._pendingCompareModes[seriesId]) {
                delete entry._pendingCompareModes[seriesId];
            }
            if (data.symbol && seriesId !== 'main' && !_activeIndicators[seriesId]) {
                if (!entry._compareSymbols) entry._compareSymbols = {};
                entry._compareSymbols[seriesId] = String(data.symbol).toUpperCase();
                if (!entry._compareLabels) entry._compareLabels = {};
                entry._compareLabels[seriesId] = _tvDisplayLabelFromSymbolInfo(data.symbolInfo || null, data.symbol);
                if (data.symbolInfo) {
                    if (!entry._compareSymbolInfo) entry._compareSymbolInfo = {};
                    entry._compareSymbolInfo[seriesId] = data.symbolInfo;
                }
            }
            _tvUpsertPayloadSeries(entry, seriesId, {
                seriesId: seriesId,
                bars: sourceBars,
                volume: data.volume || [],
                seriesType: sType,
                seriesOptions: data.seriesOptions || {},
            });
            _tvRecomputeIndicatorsForChart(resolved ? resolved.chartId : (data.chartId || _cid), seriesId);
            _tvRefreshLegendTitle(resolved ? resolved.chartId : (data.chartId || _cid));
            _tvEmitLegendRefresh(resolved ? resolved.chartId : (data.chartId || _cid));
            _tvRenderHoverLegend(resolved ? resolved.chartId : (data.chartId || _cid), null);
        });

        // Python → JS: remove a series
        bridge.on('tvchart:remove-series', function(data) {
            var entry = window.__PYWRY_TVCHARTS__[data.chartId || _cid];
            if (!entry || !entry.chart) return;
            var seriesId = data.seriesId;
            if (seriesId && entry.seriesMap[seriesId]) {
                entry.chart.removeSeries(entry.seriesMap[seriesId]);
                delete entry.seriesMap[seriesId];
                if (entry._seriesStyleAux && entry._seriesStyleAux[seriesId]) {
                    var aux = entry._seriesStyleAux[seriesId] || {};
                    var auxKeys = Object.keys(aux);
                    for (var ai = 0; ai < auxKeys.length; ai++) {
                        var key = auxKeys[ai];
                        if (key.indexOf('series_') === 0 && aux[key]) {
                            try { entry.chart.removeSeries(aux[key]); } catch (e) {}
                        }
                    }
                    delete entry._seriesStyleAux[seriesId];
                }
                if (entry._seriesRawData && entry._seriesRawData[seriesId]) {
                    delete entry._seriesRawData[seriesId];
                }
                if (entry._seriesCanonicalRawData && entry._seriesCanonicalRawData[seriesId]) {
                    delete entry._seriesCanonicalRawData[seriesId];
                }
                if (entry._seriesAuxRawData && entry._seriesAuxRawData[seriesId]) {
                    delete entry._seriesAuxRawData[seriesId];
                }
                _tvRemovePayloadSeries(entry, seriesId);
                if (entry._compareSymbols && entry._compareSymbols[seriesId]) {
                    delete entry._compareSymbols[seriesId];
                }
                if (entry._compareLabels && entry._compareLabels[seriesId]) {
                    delete entry._compareLabels[seriesId];
                }
                if (entry._compareSymbolInfo && entry._compareSymbolInfo[seriesId]) {
                    delete entry._compareSymbolInfo[seriesId];
                }
                if (entry._dataRequestSeen && entry._dataRequestSeen[seriesId]) {
                    delete entry._dataRequestSeen[seriesId];
                }
                if (entry._legendSeriesColors && entry._legendSeriesColors[seriesId]) {
                    delete entry._legendSeriesColors[seriesId];
                }
            }
            // Also remove associated volume series if any
            if (seriesId && entry.volumeMap[seriesId]) {
                entry.chart.removeSeries(entry.volumeMap[seriesId]);
                delete entry.volumeMap[seriesId];
            }

            if (seriesId) {
                _tvRecomputeIndicatorsForChart(data.chartId || _cid, seriesId);
            }
            _tvRefreshLegendTitle(data.chartId || _cid);
            _tvEmitLegendRefresh(data.chartId || _cid);
            _tvRenderHoverLegend(data.chartId || _cid, null);
        });

        // Python → JS: add markers to a series
        bridge.on('tvchart:add-markers', function(data) {
            var entry = window.__PYWRY_TVCHARTS__[data.chartId || _cid];
            if (!entry) return;
            var seriesId = data.seriesId || 'main';
            var series = entry.seriesMap[seriesId];
            if (series && data.markers) {
                // Sort markers by time (required by lightweight-charts)
                var sorted = data.markers.slice().sort(function(a, b) { return a.time - b.time; });
                series.setMarkers(sorted);
            }
        });

        // Python → JS: add a horizontal price line
        bridge.on('tvchart:add-price-line', function(data) {
            var entry = window.__PYWRY_TVCHARTS__[data.chartId || _cid];
            if (!entry) return;
            var seriesId = data.seriesId || 'main';
            var series = entry.seriesMap[seriesId];
            if (series) {
                series.createPriceLine({
                    price: data.price,
                    color: data.color || _cssVar('--pywry-tvchart-price-line', '#2196f3'),
                    lineWidth: data.lineWidth || 1,
                    lineStyle: data.lineStyle || 0,
                    axisLabelVisible: true,
                    title: data.title || '',
                });
            }
        });

        // Python → JS: fit content / scroll to position
        bridge.on('tvchart:time-scale', function(data) {
            var chartId = data.chartId || _cid;
            var entry = window.__PYWRY_TVCHARTS__[chartId];
            if (!entry || !entry.chart) return;
            if (data.fitContent) {
                entry.chart.timeScale().fitContent();
            }
            if (data.scrollTo !== undefined) {
                entry.chart.timeScale().scrollToPosition(data.scrollTo, false);
            }
            if (data.visibleRange) {
                entry.chart.timeScale().setVisibleLogicalRange(data.visibleRange);
            }
            // Signal the Python-side mutation handler that the zoom /
            // fit / scroll has been applied so it can return the
            // confirmed post-mutation state instead of blocking on a
            // timeout.  Same event name as data-response's settled
            // signal — the payload is the live chart state.
            var settledState = _tvExportState(chartId);
            bridge.emit('tvchart:data-settled', settledState || {
                chartId: chartId, error: 'not found',
            });
        });

        // Python → JS: request state export
        bridge.on('tvchart:request-state', function(data) {
            var chartId = _resolveCid(data);
            var state = _tvExportState(chartId);
            var response = state || { chartId: chartId, error: 'not found' };
            if (data && data.context) {
                response = Object.assign({}, response, { context: data.context });
            }
            bridge.emit('tvchart:state-response', response);
        });

        // Theme switching (global event from PyWry framework)
        bridge.on('pywry:update-theme', function(data) {
            var newTheme = (data && data.theme === 'light') ? 'light' : 'dark';
            var isDark = newTheme === 'dark';

            // Ensure DOM classes are correct before reading CSS variables
            var htmlEl = document.documentElement;
            htmlEl.classList.remove('dark', 'light', 'pywry-theme-dark', 'pywry-theme-light');
            htmlEl.classList.add(newTheme);
            htmlEl.classList.add(isDark ? 'pywry-theme-dark' : 'pywry-theme-light');

            // Only update THIS widget's chart
            var chartId = (data && data.chartId) || _cid;
            if (chartId) {
                _tvApplyThemeToChart(chartId, newTheme);
            } else {
                _tvApplyThemeToAll(newTheme);
            }
        });

        // -----------------------------------------------------------------
        // Toolbar event handlers (Browser → JS chart actions)
        // -----------------------------------------------------------------

        // Chart type change (Select dropdown)
        bridge.on('tvchart:chart-type-change', function(data) {
            var displayName = data.value || data.selected || 'Candles';
            var styleCfg = _tvResolveChartStyle(displayName);
            var baseType = styleCfg.seriesType;
            var resolved = _tvResolveChartEntry((data && data.chartId) || _cid);
            if (!resolved || !resolved.entry) return;
            var entry = resolved.entry;

            // Save the current visible range so we can restore after switching
            var savedRange = null;
            try { savedRange = entry.chart.timeScale().getVisibleLogicalRange(); } catch (e) {}

            // Chart-type selector controls only one series on one chart.
            var requestedSeriesId = data && data.seriesId ? String(data.seriesId) : 'main';
            var mainKey = (entry.seriesMap && entry.seriesMap[requestedSeriesId])
                ? requestedSeriesId
                : (entry.seriesMap && entry.seriesMap.main ? 'main' : (Object.keys(entry.seriesMap || {})[0] || null));
            if (!mainKey) return;
            var oldSeries = entry.seriesMap[mainKey];
            if (!oldSeries) return;

            // Clean up any previous style-auxiliary series (e.g. HLC area fills)
            if (entry._seriesStyleAux && entry._seriesStyleAux[mainKey]) {
                var prevAux = entry._seriesStyleAux[mainKey];
                var prevAuxKeys = Object.keys(prevAux);
                for (var pai = 0; pai < prevAuxKeys.length; pai++) {
                    var pak = prevAuxKeys[pai];
                    if (pak.indexOf('series_') === 0 && prevAux[pak]) {
                        try { entry.chart.removeSeries(prevAux[pak]); } catch (e) {}
                    }
                }
                delete entry._seriesStyleAux[mainKey];
            }

            var payloadSeries = _tvFindPayloadSeries(entry, mainKey);
            var payloadBars = (payloadSeries && Array.isArray(payloadSeries.bars)) ? payloadSeries.bars : [];
            var fallbackBars = (entry._seriesRawData && Array.isArray(entry._seriesRawData[mainKey])) ? entry._seriesRawData[mainKey] : [];

            if (!entry._seriesCanonicalRawData) entry._seriesCanonicalRawData = {};
            var canonicalBars = entry._seriesCanonicalRawData[mainKey];
            if (!Array.isArray(canonicalBars) || !canonicalBars.length) {
                if (_tvLooksLikeOhlcBars(payloadBars)) {
                    canonicalBars = payloadBars;
                } else if (_tvLooksLikeOhlcBars(fallbackBars)) {
                    canonicalBars = fallbackBars;
                }
                if (Array.isArray(canonicalBars) && canonicalBars.length) {
                    entry._seriesCanonicalRawData[mainKey] = canonicalBars;
                }
            }

            var rawBars = (Array.isArray(canonicalBars) && canonicalBars.length)
                ? canonicalBars
                : (payloadBars.length ? payloadBars : fallbackBars);

            var sOpts = _tvBuildSeriesOptions(
                (payloadSeries && payloadSeries.seriesOptions) ? payloadSeries.seriesOptions : {},
                baseType,
                entry.theme
            );

            // Apply style-specific option overrides (e.g. hollow candles, step line)
            var patch = styleCfg.optionPatch;
            if (patch) {
                for (var pk in patch) {
                    if (patch.hasOwnProperty(pk)) sOpts[pk] = patch[pk];
                }
            }

            var targetPaneIndex = 0;
            if (!_tvIsMainSeriesId(mainKey) && entry._comparePaneBySeries && entry._comparePaneBySeries[mainKey] !== undefined) {
                targetPaneIndex = entry._comparePaneBySeries[mainKey];
            }

            if (_tvIsMainSeriesId(mainKey)) {
                sOpts.priceScaleId = _tvResolveScalePlacement(entry);
                if (entry._comparePaneBySeries && entry._comparePaneBySeries.main !== undefined) {
                    delete entry._comparePaneBySeries.main;
                }
            }

            // For Baseline, compute a baseValue at the 50% level of the data range
            // so the chart splits into above/below zones correctly.
            if (baseType === 'Baseline' && !sOpts.baseValue) {
                sOpts.baseValue = { type: 'price', price: _tvComputeBaselineValue(rawBars, 50), _level: 50 };
            }

            // Build data using the style-aware transform (handles HLC, Heikin Ashi, etc.)
            var bars = _tvBuildBarsForChartStyle(rawBars, displayName);

            // Add new series FIRST so pane 0 is never empty (removing the
            // last series in a pane destroys the pane and renumbers the rest).
            if (styleCfg.composite === 'hlcArea') {
                // HLC area: filled band between high and low, split at the
                // close line into an up-color zone and a down-color zone.
                // Achieved with 4 layered Area series (masking technique):
                //   1. High area  – teal fill from high downward
                //   2. Close mask – opaque background erases teal below close
                //   3. Close area – pink fill from close downward + blue close line
                //   4. Low mask   – opaque background erases pink below low + pink low line
                var bgColor = _cssVar('--pywry-tvchart-bg');
                var hlcHighColor = _cssVar('--pywry-tvchart-hlcarea-high');
                var hlcLowColor = _cssVar('--pywry-tvchart-hlcarea-low');
                var hlcCloseColor = _cssVar('--pywry-tvchart-hlcarea-close');
                var hlcFillUp = _cssVar('--pywry-tvchart-hlcarea-fill-up');
                var hlcFillDown = _cssVar('--pywry-tvchart-hlcarea-fill-down');
                var scaleId = sOpts.priceScaleId || (_tvIsMainSeriesId(mainKey) ? _tvResolveScalePlacement(entry) : undefined);

                var auxBase = {
                    crosshairMarkerVisible: false,
                    lastValueVisible: false,
                    priceLineVisible: false,
                };
                if (scaleId) auxBase.priceScaleId = scaleId;

                // Build data arrays from raw OHLC bars
                var highData = [], lowData = [], closeData = [];
                for (var bi = 0; bi < rawBars.length; bi++) {
                    var rb = rawBars[bi] || {};
                    if (rb.time == null) continue;
                    var bh = Number(rb.high);
                    var bl = Number(rb.low);
                    var bc = Number(rb.close !== undefined ? rb.close : rb.value);
                    if (!isFinite(bh) || !isFinite(bl) || !isFinite(bc)) continue;
                    highData.push({ time: rb.time, value: bh });
                    lowData.push({ time: rb.time, value: bl });
                    closeData.push({ time: rb.time, value: bc });
                }

                // Layer 1: High area (teal fill from high line down)
                var highSeries = _tvAddSeriesCompat(entry.chart, 'Area', _tvMerge(auxBase, {
                    topColor: hlcFillUp, bottomColor: hlcFillUp,
                    lineColor: hlcHighColor, lineWidth: 1,
                }), targetPaneIndex);

                // Layer 2: Close mask (opaque background erases teal below close)
                var closeMaskSeries = _tvAddSeriesCompat(entry.chart, 'Area', _tvMerge(auxBase, {
                    topColor: bgColor, bottomColor: bgColor,
                    lineColor: 'transparent', lineWidth: 0,
                }), targetPaneIndex);

                // Layer 3: Close area (pink fill from close down + blue close line)
                var closeAreaSeries = _tvAddSeriesCompat(entry.chart, 'Area', _tvMerge(auxBase, {
                    topColor: hlcFillDown, bottomColor: hlcFillDown,
                    lineColor: hlcCloseColor, lineWidth: 2,
                }), targetPaneIndex);

                // Layer 4: Low mask (opaque background erases pink below low + pink low line)
                var lowMaskSeries = _tvAddSeriesCompat(entry.chart, 'Area', _tvMerge(auxBase, {
                    topColor: bgColor, bottomColor: bgColor,
                    lineColor: hlcLowColor, lineWidth: 1,
                }), targetPaneIndex);

                try { highSeries.setData(highData); } catch (e) {}
                try { closeMaskSeries.setData(closeData); } catch (e) {}
                try { closeAreaSeries.setData(closeData); } catch (e) {}
                try { lowMaskSeries.setData(lowData); } catch (e) {}
                try { entry.chart.removeSeries(oldSeries); } catch (e) {}

                // The close area series is the "main" series (has the close line
                // and receives crosshair/price tracking in the legend).
                var newSeries = closeAreaSeries;
                entry.seriesMap[mainKey] = newSeries;
                if (!entry._seriesStyleAux) entry._seriesStyleAux = {};
                entry._seriesStyleAux[mainKey] = {
                    series_high: highSeries,
                    series_closeMask: closeMaskSeries,
                    series_lowMask: lowMaskSeries,
                };

                bars = closeData;
            } else {
                var newSeries = _tvAddSeriesCompat(entry.chart, baseType, sOpts, targetPaneIndex);
                try { newSeries.setData(bars); } catch (e) {}
                try { entry.chart.removeSeries(oldSeries); } catch (e) {}
                entry.seriesMap[mainKey] = newSeries;
            }

            if (!entry._seriesRawData) entry._seriesRawData = {};
            entry._seriesRawData[mainKey] = bars;

            // Store the display name so settings and legend can reference it
            entry._chartDisplayStyle = displayName;

            // Persist only the new seriesType and bars — NOT sOpts.  sOpts
            // contains the style-specific optionPatch (e.g. Hollow candles'
            // transparent ``upColor``), and merging it into the persisted
            // baseline contaminates future switches: "Hollow candles" →
            // "Candles" would leave ``upColor`` transparent because Candles'
            // empty optionPatch has nothing to reset it with.  The pristine
            // baseline in ``payloadSeries.seriesOptions`` is re-read on
            // every switch via ``_tvBuildSeriesOptions`` — don't poison it.
            _tvUpsertPayloadSeries(entry, mainKey, {
                seriesType: baseType,
                bars: rawBars,
            });

            if (entry.payload) {
                entry.payload.seriesType = baseType;
                if (entry.payload.series && Array.isArray(entry.payload.series) && entry.payload.series[0]) {
                    entry.payload.series[0].seriesType = baseType;
                }
            }

            // Restore the zoom/pan position (or fit if no saved range)
            if (savedRange && savedRange.from != null && savedRange.to != null) {
                entry.chart.timeScale().setVisibleLogicalRange(savedRange);
            } else {
                entry.chart.timeScale().fitContent();
            }
            _tvRenderHoverLegend(resolved.chartId, null);
        });

        // Dark mode toggle — updates THIS widget's UI only.
        bridge.on('tvchart:toggle-dark-mode', function(data) {
            var isDark = data.value === true || data.checked === true;
            var newTheme = isDark ? 'dark' : 'light';

            // Update documentElement theme classes so CSS variables resolve correctly
            var htmlEl = document.documentElement;
            htmlEl.classList.remove('dark', 'light', 'pywry-theme-dark', 'pywry-theme-light');
            htmlEl.classList.add(newTheme);
            htmlEl.classList.add(isDark ? 'pywry-theme-dark' : 'pywry-theme-light');

            // Only update THIS widget's container — not all widgets on the page
            var chartId = (data && data.chartId) || _cid;
            var uiRoot = chartId ? _tvResolveUiRoot(chartId) : null;
            if (uiRoot && uiRoot !== document) {
                var containers = uiRoot.querySelectorAll('.pywry-widget, .pywry-container, .pywry-theme-dark, .pywry-theme-light');
                containers.forEach(function(el) {
                    el.classList.remove('pywry-theme-dark', 'pywry-theme-light');
                    el.classList.add(isDark ? 'pywry-theme-dark' : 'pywry-theme-light');
                });
                // Walk up to .pywry-widget ancestor too
                var widgetEl = uiRoot.closest && uiRoot.closest('.pywry-widget');
                if (widgetEl) {
                    widgetEl.classList.remove('pywry-theme-dark', 'pywry-theme-light');
                    widgetEl.classList.add(isDark ? 'pywry-theme-dark' : 'pywry-theme-light');
                }
            }

            // Only apply theme to THIS widget's chart
            if (chartId) {
                _tvApplyThemeToChart(chartId, newTheme);
            } else {
                _tvApplyThemeToAll(newTheme);
            }

            // Notify Python (sendEvent only — no local re-dispatch to avoid
            // double-firing the pywry:update-theme listener).
            if (bridge && bridge.sendEvent) {
                bridge.sendEvent('pywry:update-theme', { theme: newTheme });
            }
        });

        // Settings button
        bridge.on('tvchart:show-settings', function(data) {
            var chartId = _tvResolveChartId(data.chartId || _cid);
            var ds = chartId ? window.__PYWRY_DRAWINGS__[chartId] : null;
            if (chartId && ds && _drawSelectedIdx >= 0 && _drawSelectedChart === chartId) {
                _tvShowDrawingSettings(chartId, _drawSelectedIdx);
                return;
            }
            if (chartId) _tvShowChartSettings(chartId);
        });

        // Indicators button
        bridge.on('tvchart:show-indicators', function(data) {
            var chartId = data.chartId || _cid;
            _tvShowIndicatorsPanel(chartId);
        });

        bridge.on('tvchart:add-indicator', function(data) {
            var chartId = data.chartId || _cid;
            var def = {
                name: data.name || '',
                key: data.key || undefined,
                defaultPeriod: data.period !== undefined ? data.period : (data.defaultPeriod || 0),
                _color: data.color || undefined,
                _source: data.source || undefined,
                _method: data.method || undefined,
                _multiplier: data.multiplier || undefined,
                _maType: data.maType || undefined,
                _offset: data.offset || undefined,
                _fromIndex: data.fromIndex,
                _toIndex: data.toIndex,
            };
            _tvAddIndicator(def, chartId);
        });

        bridge.on('tvchart:remove-indicator', function(data) {
            var seriesId = data.seriesId;
            if (seriesId) _tvRemoveIndicator(seriesId);
        });

        bridge.on('tvchart:list-indicators', function(data) {
            var chartId = data.chartId || _cid;
            var resolved = _tvResolveChartEntry(chartId);
            var listEntry = resolved ? resolved.entry : null;
            var result = [];
            var keys = Object.keys(_activeIndicators);
            for (var i = 0; i < keys.length; i++) {
                var info = _activeIndicators[keys[i]];
                if (!info || info.chartId !== chartId) continue;
                var out = {
                    seriesId: keys[i],
                    name: info.name,
                    type: info.type,
                    period: info.period || 0,
                    color: info.color,
                    group: info.group || null,
                    sourceSeriesId: info.sourceSeriesId || null,
                    secondarySeriesId: info.secondarySeriesId || null,
                    isSubplot: !!info.isSubplot,
                    primarySource: info.primarySource || null,
                    secondarySource: info.secondarySource || null,
                };
                // Resolve the secondary series back to its ticker symbol
                // so agents describing e.g. a Spread indicator know what
                // it's spreading against.
                if (info.secondarySeriesId && listEntry && listEntry._compareSymbols) {
                    var sym = listEntry._compareSymbols[info.secondarySeriesId];
                    out.secondarySymbol = sym ? String(sym) : null;
                }
                result.push(out);
            }
            bridge.emit('tvchart:list-indicators-response', {
                chartId: chartId,
                indicators: result,
                context: data.context || null,
            });
        });

        // Log scale toggle (legacy event fallback)
        bridge.on('tvchart:log-scale', function(data) {
            var isLog = data.value === true || data.checked === true;
            _tvApplyLogScale(isLog, data.chartId || _cid);
        });

        // Auto scale toggle (legacy event fallback)
        bridge.on('tvchart:auto-scale', function(data) {
            var isAuto = data.value === true || data.checked === true;
            _tvApplyAutoScale(isAuto, data.chartId || _cid);
        });

        // Data interval/frequency change (top bar) — emits to Python for data re-fetch
        bridge.on('tvchart:interval-change', function(data) {
            var interval = data.value || '1d';
            // Deselect all time-range tabs — interval change always shows ALL data
            var tabs = document.querySelectorAll('.pywry-tab[data-target-interval]');
            for (var t = 0; t < tabs.length; t++) {
                tabs[t].classList.remove('pywry-tab-active');
            }
            var chartId = _tvResolveChartId((data && data.chartId) || _cid);

            // In datafeed mode, ask Python to fetch bars at the new
            // resolution (with aggregation for unsupported intervals like
            // 3d, 2w).  The tvchart:data-response handler will destroy
            // and recreate the chart with the pre-fetched bars so
            // getBars is bypassed entirely.
            var resolved = _tvResolveChartEntry(chartId);
            var entry = resolved ? resolved.entry : null;
            if (entry && entry.payload && entry.payload.useDatafeed) {
                var currentInterval = (entry.payload && entry.payload.interval) || '';
                if (interval === currentInterval) return; // no-op if same interval

                var mainSymbol = '';
                if (entry.payload.series && entry.payload.series[0] && entry.payload.series[0].symbol) {
                    mainSymbol = String(entry.payload.series[0].symbol);
                } else if (entry._resolvedSymbolInfo && entry._resolvedSymbolInfo.main) {
                    mainSymbol = String(entry._resolvedSymbolInfo.main.symbol || entry._resolvedSymbolInfo.main.ticker || '');
                }

                bridge.emit('tvchart:data-request', {
                    chartId: resolved ? resolved.chartId : chartId,
                    symbol: mainSymbol,
                    seriesId: 'main',
                    interval: interval,
                    resolution: interval,
                    periodParams: {
                        from: 0,
                        to: Math.floor(Date.now() / 1000),
                        countBack: 300,
                        firstDataRequest: true,
                    },
                });

                // Also request data for compare symbols at the new interval
                if (entry._compareSymbols) {
                    var cmpKeys = Object.keys(entry._compareSymbols);
                    for (var ci = 0; ci < cmpKeys.length; ci++) {
                        var cmpSid = cmpKeys[ci];
                        var cmpSym = entry._compareSymbols[cmpSid];
                        if (!cmpSym) continue;
                        bridge.emit('tvchart:data-request', {
                            chartId: resolved ? resolved.chartId : chartId,
                            symbol: cmpSym,
                            symbolInfo: entry._compareSymbolInfo ? entry._compareSymbolInfo[cmpSid] : null,
                            seriesId: cmpSid,
                            interval: interval,
                            resolution: interval,
                            periodParams: {
                                from: 0,
                                to: Math.floor(Date.now() / 1000),
                                countBack: 300,
                                firstDataRequest: true,
                            },
                        });
                    }
                }
                return;
            }

            // Non-datafeed mode: notify Python so it can supply new data
            _tvEmitIntervalDataRequests(chartId, interval);
        });

        // Time range preset (TabGroup) — zoom only, never changes interval.
        bridge.on('tvchart:time-range', function(data) {
            var range = data.value || data.selected || '1y';
            var chartId = data.chartId || _cid;
            var resolved = _tvResolveChartEntry(chartId);
            var entry = resolved ? resolved.entry : null;
            if (entry && entry.chart) {
                _tvApplyTimeRangeSelection(entry, range);
            }
            // Signal mutation completion for Python-side
            // ``_wait_for_data_settled`` so the tool returns confirmed
            // state instead of blocking on the timeout.
            var settledCid = resolved ? resolved.chartId : chartId;
            var settledState = _tvExportState(settledCid);
            bridge.emit('tvchart:data-settled', settledState || {
                chartId: settledCid, error: 'not found',
            });
        });

        bridge.on('tvchart:time-range-picker', function(data) {
            var chartId = (data && data.chartId) || _cid;
            var resolved = _tvResolveChartEntry(chartId);
            var entry = resolved ? resolved.entry : null;
            if (!entry || !entry.chart) return;
            _tvPromptDateRangeAndApply(entry);
        });

        // Screenshot
        bridge.on('tvchart:screenshot', function(data) {
            var chartId = (data && data.chartId) || _cid;
            var resolved = _tvResolveChartEntry(chartId);
            var entry = resolved ? resolved.entry : null;
            if (!entry || !entry.chart) return;

            // Use the chart's takeScreenshot method
            try {
                var canvas = entry.chart.takeScreenshot();
                // Open screenshot in new window
                var w = window.open('', '_blank');
                if (w) {
                    w.document.write('<img src="' + canvas.toDataURL() + '"/>');
                }
            } catch(e) {
                console.warn('[pywry:tvchart] Screenshot failed:', e);
            }
        });

        // Undo — revert last chart action (drawing, indicator, etc.)
        bridge.on('tvchart:undo', function() {
            _tvPerformUndo();
        });

        // Redo — re-apply last undone action
        bridge.on('tvchart:redo', function() {
            _tvPerformRedo();
        });

        // Compare — open symbol entry panel.  Optional ``query`` drives
        // the panel programmatically: search + auto-add the matching
        // ticker as a compare series, so MCP callers can confirm the
        // compare actually appeared in state.compareSymbols.
        bridge.on('tvchart:compare', function(data) {
            var chartId = _tvResolveChartId((data && data.chartId) || _cid);
            if (!chartId) return;
            _tvShowComparePanel(chartId, {
                query: data && data.query,
                autoAdd: data && data.autoAdd !== false,
                symbolType: data && data.symbolType,
                exchange: data && data.exchange,
            });
        });

        // Symbol search — open the symbol search dialog. Optional
        // `query` pre-fills the input; `autoSelect` (default true when
        // `query` is provided) picks the matching/first result.
        // `symbolType` / `exchange` narrow the datafeed search.
        bridge.on('tvchart:symbol-search', function(data) {
            var chartId = _tvResolveChartId((data && data.chartId) || _cid);
            if (!chartId) return;
            _tvShowSymbolSearchDialog(chartId, {
                query: data && data.query,
                autoSelect: data && data.autoSelect,
                symbolType: data && data.symbolType,
                exchange: data && data.exchange,
            });
        });

        bridge.on('tvchart:datafeed-search-response', function(data) {
            data = data || {};
            var requestId = data.requestId;
            if (!requestId) return;
            var cb = window.__PYWRY_TVCHART_DATAFEED__.pendingSearch[requestId];
            if (!cb) return;
            delete window.__PYWRY_TVCHART_DATAFEED__.pendingSearch[requestId];
            cb(data);
        });

        bridge.on('tvchart:datafeed-resolve-response', function(data) {
            data = data || {};
            var requestId = data.requestId;
            if (!requestId) return;
            var cb = window.__PYWRY_TVCHART_DATAFEED__.pendingResolve[requestId];
            if (!cb) return;
            delete window.__PYWRY_TVCHART_DATAFEED__.pendingResolve[requestId];
            cb(data);
        });

        bridge.on('tvchart:datafeed-history-response', function(data) {
            data = data || {};
            var requestId = data.requestId;
            if (!requestId) return;
            var cb = window.__PYWRY_TVCHART_DATAFEED__.pendingHistory[requestId];
            if (!cb) return;
            delete window.__PYWRY_TVCHART_DATAFEED__.pendingHistory[requestId];
            cb(data);
        });

        // Datafeed — config response (onReady)
        bridge.on('tvchart:datafeed-config-response', function(data) {
            data = data || {};
            var requestId = data.requestId;
            if (!requestId) return;
            var cb = window.__PYWRY_TVCHART_DATAFEED__.pendingConfig[requestId];
            if (!cb) return;
            delete window.__PYWRY_TVCHART_DATAFEED__.pendingConfig[requestId];
            cb(data);
        });

        // Datafeed — real-time bar update (subscribeBars push)
        bridge.on('tvchart:datafeed-bar-update', function(data) {
            data = data || {};
            var guid = data.listenerGuid;
            if (!guid) return;
            var sub = window.__PYWRY_TVCHART_DATAFEED__.subscriptions[guid];
            if (!sub || !sub.onTick) return;
            var bar = data.bar;
            if (bar && typeof bar === 'object') {
                sub.onTick(bar);
            }
        });

        // Datafeed — reset cache signal
        bridge.on('tvchart:datafeed-reset-cache', function(data) {
            data = data || {};
            var guid = data.listenerGuid;
            if (!guid) return;
            var sub = window.__PYWRY_TVCHART_DATAFEED__.subscriptions[guid];
            if (sub && typeof sub.onResetCacheNeeded === 'function') {
                sub.onResetCacheNeeded();
            }
        });

        // Datafeed — marks response (getMarks)
        bridge.on('tvchart:datafeed-marks-response', function(data) {
            data = data || {};
            var requestId = data.requestId;
            if (!requestId) return;
            var cb = window.__PYWRY_TVCHART_DATAFEED__.pendingMarks[requestId];
            if (!cb) return;
            delete window.__PYWRY_TVCHART_DATAFEED__.pendingMarks[requestId];
            cb(data.marks || []);
        });

        // Datafeed — timescale marks response (getTimescaleMarks)
        bridge.on('tvchart:datafeed-timescale-marks-response', function(data) {
            data = data || {};
            var requestId = data.requestId;
            if (!requestId) return;
            var cb = window.__PYWRY_TVCHART_DATAFEED__.pendingTimescaleMarks[requestId];
            if (!cb) return;
            delete window.__PYWRY_TVCHART_DATAFEED__.pendingTimescaleMarks[requestId];
            cb(data.marks || []);
        });

        // Datafeed — server time response (getServerTime)
        bridge.on('tvchart:datafeed-server-time-response', function(data) {
            data = data || {};
            var requestId = data.requestId;
            if (!requestId) return;
            var cb = window.__PYWRY_TVCHART_DATAFEED__.pendingServerTime[requestId];
            if (!cb) return;
            delete window.__PYWRY_TVCHART_DATAFEED__.pendingServerTime[requestId];
            cb(data.time || Math.floor(Date.now() / 1000));
        });

        // Fullscreen — toggle fullscreen on the chart wrapper
        bridge.on('tvchart:fullscreen', function() {
            var resolved = _tvResolveChartEntry(_cid);
            var entry = resolved ? resolved.entry : null;
            var el = (entry && entry.container)
                ? entry.container.closest('.pywry-wrapper-inside') || entry.container
                : document.querySelector('.pywry-wrapper-inside') || document.querySelector('.pywry-tvchart-container');
            if (!el) return;
            if (!document.fullscreenElement) {
                el.requestFullscreen().catch(function() {});
            } else {
                document.exitFullscreen().catch(function() {});
            }
        });

        // Show/Hide drawings
        bridge.on('tvchart:tool-visibility', function(data) {
            var chartId = _resolveCid(data);
            var ds = chartId ? window.__PYWRY_DRAWINGS__[chartId] : null;
            if (ds && ds.canvas) {
                var vis = ds.canvas.style.display !== 'none';
                ds.canvas.style.display = vis ? 'none' : '';
                if (ds.uiLayer) ds.uiLayer.style.display = vis ? 'none' : '';
            }
        });

        // Lock drawings (disable interaction)
        bridge.on('tvchart:tool-lock', function(data) {
            var chartId = _resolveCid(data);
            var ds = chartId ? window.__PYWRY_DRAWINGS__[chartId] : null;
            if (ds) {
                ds._locked = !ds._locked;
            }
        });

        // Save state → emit back to Python with full chart data + raw bars
        bridge.on('tvchart:save-state', function(data) {
            var chartId = (data && data.chartId) || _cid;
            var state = _tvExportState(chartId);
            if (state) {
                bridge.emit('tvchart:state-response', state);
            }
        });

        // Save layout → emit layout-only (annotations + indicators, no raw data)
        bridge.on('tvchart:save-layout', function(data) {
            var targetId = _tvResolveChartId(data && data.chartId ? data.chartId : _cid);
            if (!targetId) return;
            var layout = _tvExportLayout(targetId);
            if (!layout) return;

            var explicitName = data && data.name ? String(data.name) : '';
            if (explicitName) {
                var saveName = explicitName || _tvDefaultLayoutName(targetId);
                var persistedNamed = _tvLayoutPersist(targetId, saveName, layout);
                if (persistedNamed) _tvLayoutSetActive(targetId, persistedNamed);
                bridge.emit('tvchart:layout-response', layout);
                return;
            }

            var st = _tvLayoutActiveState(targetId);
            var index = _tvLayoutLoadIndex(targetId);
            var activeRow = null;
            for (var i = 0; i < index.length; i++) {
                if (String(index[i].id || '') === String(st.id || '')) {
                    activeRow = index[i];
                    break;
                }
            }

            if (activeRow && activeRow.name) {
                var persistedActive = _tvLayoutPersist(targetId, activeRow.name, layout, {
                    overwriteExisting: true,
                });
                if (persistedActive) _tvLayoutSetActive(targetId, persistedActive);
                bridge.emit('tvchart:layout-response', layout);
                return;
            }

            _tvPromptSaveLayout(targetId, _tvDefaultLayoutName(targetId), function(chosenName) {
                var finalName = chosenName || _tvDefaultLayoutName(targetId);
                var persisted = _tvLayoutPersist(targetId, finalName, layout, {
                    overwriteExisting: true,
                });
                if (persisted) _tvLayoutSetActive(targetId, persisted);
                bridge.emit('tvchart:layout-response', layout);
            });
        });

        // Open layout → open local layout picker and apply selection.
        bridge.on('tvchart:open-layout', function(data) {
            var cid = _tvResolveChartId(data && data.chartId ? data.chartId : _cid);
            _tvPromptOpenLayout(cid);
            bridge.emit('tvchart:open-layout-request', {});
        });

        // Document-level handlers (click/keydown on menus, tool groups) must
        // only be registered once — they use _tvGetBridge(chartId) to resolve
        // the correct per-widget bridge dynamically.
        if (!window.__PYWRY_TVCHART_DOC_HANDLERS__) {
        window.__PYWRY_TVCHART_DOC_HANDLERS__ = true;

        // ---- Save split-button dropdown behaviour ----
        (function() {
            function closeSaveMenu() {
                var chartId = _tvResolveChartIdFromElement(document.activeElement);
                var m = _tvScopedById(chartId, 'tvchart-save-menu');
                if (m) m.classList.remove('open');
                _tvRefreshLegendVisibility(chartId);
            }
            // Caret toggles dropdown
            document.addEventListener('click', function(e) {
                var chartId = _tvResolveChartIdFromElement(e.target);
                var caret = e.target.closest('#tvchart-save-caret');
                var menu = _tvScopedById(chartId, 'tvchart-save-menu');
                if (caret && menu) {
                    e.stopPropagation();
                    menu.classList.toggle('open');
                    _tvRefreshLegendVisibility(chartId);
                    return;
                }
                // Menu item click → emit the event, close menu
                var item = e.target.closest('.tvchart-save-menu-item');
                if (item) {
                    var action = item.getAttribute('data-action') || '';
                    var payload = {
                        chartId: chartId,
                        componentId: item.getAttribute('data-component-id') || '',
                    };
                    if (action === 'save-layout') {
                        _tvGetBridge(chartId).emit('tvchart:save-layout', payload);
                    } else if (action === 'make-copy') {
                        var st = _tvLayoutActiveState(chartId);
                        var fallback = (st.name ? st.name + ' copy' : _tvDefaultLayoutName(chartId));
                        var layoutCopy = _tvExportLayout(chartId);
                        if (layoutCopy) {
                            _tvPromptSaveLayout(chartId, fallback, function(chosenName) {
                                var finalName = chosenName || fallback;
                                var persisted = _tvLayoutPersist(chartId, finalName, layoutCopy, {
                                    overwriteExisting: false,
                                });
                                if (persisted) _tvLayoutSetActive(chartId, persisted);
                                _tvGetBridge(chartId).emit('tvchart:layout-response', layoutCopy);
                            });
                        }
                    } else if (action === 'rename-layout') {
                        var st2 = _tvLayoutActiveState(chartId);
                        if (st2 && st2.id) {
                            _tvPromptSaveLayout(chartId, st2.name || '', function(nextName) {
                                var renamed = _tvLayoutRenameById(chartId, st2.id, nextName);
                                if (renamed) _tvLayoutSetActive(chartId, renamed);
                            });
                        }
                    } else if (action === 'open-layout') {
                        _tvGetBridge(chartId).emit('tvchart:open-layout', payload);
                    }
                    if (menu) menu.classList.remove('open');
                    _tvRefreshLegendVisibility(chartId);
                    return;
                }
                // Click outside → close
                if (menu && !e.target.closest('.tvchart-save-split')) {
                    menu.classList.remove('open');
                    _tvRefreshLegendVisibility(chartId);
                }
            }, true);
            // Keyboard shortcut Ctrl+S → save layout
            document.addEventListener('keydown', function(e) {
                if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                    e.preventDefault();
                    var _saveChartId = _tvResolveChartIdFromElement(document.activeElement);
                    var _saveBridge = _tvGetBridge(_saveChartId);
                    if (_saveBridge) {
                        _saveBridge.emit('tvchart:save-layout', {
                            chartId: _saveChartId,
                        });
                    }
                }
                // Ctrl+Z → undo, Ctrl+Shift+Z / Ctrl+Y → redo
                if ((e.ctrlKey || e.metaKey) && !e.altKey) {
                    if (e.key === 'z' && !e.shiftKey) {
                        e.preventDefault();
                        _tvPerformUndo();
                    } else if ((e.key === 'z' && e.shiftKey) || e.key === 'y') {
                        e.preventDefault();
                        _tvPerformRedo();
                    }
                }
            });

            var ids = Object.keys(window.__PYWRY_TVCHARTS__);
            for (var i = 0; i < ids.length; i++) {
                _tvRefreshSaveMenu(ids[i]);
            }
        })();

        // ---- Chart-type dropdown menu (static markup) ----
        (function() {
            document.addEventListener('click', function(e) {
                var chartId = _tvResolveChartIdFromElement(e.target);
                var menu = _tvScopedById(chartId, 'tvchart-chart-type-menu');
                if (e.target.closest('#tvchart-chart-type-icon')) {
                    e.stopPropagation();
                    if (menu) {
                        var opening = !menu.classList.contains('open');
                        menu.style.display = '';  // clear inline style
                        menu.classList.toggle('open');
                        if (!opening) menu.style.display = 'none';
                    }
                    _tvRefreshLegendVisibility(chartId);
                    return;
                }
                var item = e.target.closest('.tvchart-chart-type-item');
                if (item && menu && menu.contains(item)) {
                    var type = item.getAttribute('data-type');
                    menu.querySelectorAll('.tvchart-chart-type-item').forEach(function(el) { el.classList.remove('selected'); });
                    item.classList.add('selected');
                    menu.classList.remove('open');
                    menu.style.display = 'none';
                    _tvRefreshLegendVisibility(chartId);
                    var _ctBridge = _tvGetBridge(chartId);
                    if (_ctBridge) {
                        _ctBridge.emit('tvchart:chart-type-change', {
                            value: type,
                            chartId: chartId,
                            seriesId: 'main',
                            componentId: 'tvchart-chart-type-icon',
                        });
                    }
                    return;
                }
                if (menu && !e.target.closest('.tvchart-chart-type-anchor')) {
                    menu.classList.remove('open');
                    menu.style.display = 'none';
                    _tvRefreshLegendVisibility(chartId);
                }
            }, true);
        })();

        // ---- Interval dropdown (static markup) ----
        (function() {
            document.addEventListener('click', function(e) {
                var chartId = _tvResolveChartIdFromElement(e.target);
                var menu = _tvScopedById(chartId, 'tvchart-interval-menu');
                if (e.target.closest('#tvchart-interval-btn')) {
                    e.stopPropagation();
                    if (menu) {
                        var opening = !menu.classList.contains('open');
                        menu.style.display = '';  // clear inline style
                        menu.classList.toggle('open');
                        if (!opening) menu.style.display = 'none';
                    }
                    _tvRefreshLegendVisibility(chartId);
                    return;
                }
                var item = e.target.closest('.tvchart-interval-item');
                if (item && menu && menu.contains(item)) {
                    if (item.classList.contains('disabled')) {
                        return;
                    }
                    var iv = item.getAttribute('data-interval');
                    menu.querySelectorAll('.tvchart-interval-item').forEach(function(el) { el.classList.remove('selected'); });
                    item.classList.add('selected');
                    menu.classList.remove('open');
                    menu.style.display = 'none';
                    _tvRefreshLegendVisibility(chartId);
                    _tvSetIntervalUi(chartId, iv);
                    var _ivBridge = _tvGetBridge(chartId);
                    if (_ivBridge) {
                        _ivBridge.emit('tvchart:interval-change', { value: iv, chartId: chartId, componentId: 'tvchart-interval-btn' });
                    }
                    return;
                }
                if (menu && !e.target.closest('.tv-interval-anchor')) {
                    menu.classList.remove('open');
                    menu.style.display = 'none';
                    _tvRefreshLegendVisibility(chartId);
                }
            }, true);
        })();

        } // end __PYWRY_TVCHART_DOC_HANDLERS__ guard (menus)

        // Drawing tool selection — highlight active tool AND activate drawing mode
        // Only standalone tools (not in a group flyout) are in this map.
        var toolNameMap = {
            'tvchart:tool-cursor': 'cursor',
            'tvchart:tool-crosshair': 'crosshair',
            'tvchart:tool-magnet': 'magnet',
            'tvchart:tool-eraser': 'eraser'
        };
        var drawingToolEvents = Object.keys(toolNameMap);
        drawingToolEvents.forEach(function(evtName) {
            bridge.on(evtName, function(data) {
                _tvHideToolGroupFlyout();
                var clicked = data.componentId
                    ? _tvScopedById(data.chartId || _cid, data.componentId)
                    : null;
                var chartId = _tvResolveChartIdFromElement(clicked || document.activeElement);
                var ds = window.__PYWRY_DRAWINGS__[chartId];

                // Remove active class from this chart's toolbar icons
                var allIcons = _tvScopedQueryAll(chartId, '.pywry-toolbar-left .pywry-icon-btn');
                if (allIcons) allIcons.forEach(function(el) { el.classList.remove('active'); });
                if (clicked) clicked.classList.add('active');

                var toolName = toolNameMap[evtName] || 'cursor';

                // Eraser: clear this chart's drawings
                if (toolName === 'eraser') {
                    _tvClearDrawings(chartId);
                    _tvSetDrawTool(chartId, 'cursor');
                    if (allIcons) allIcons.forEach(function(el) { el.classList.remove('active'); });
                    var cursorBtn = _tvScopedById(chartId, 'tvchart-tool-cursor');
                    if (cursorBtn) cursorBtn.classList.add('active');
                    return;
                }

                // Toggle: pressing same tool again reverts to cursor
                var currentTool = ds ? ds._activeTool : 'cursor';
                if (toolName === currentTool) {
                    _tvSetDrawTool(chartId, 'cursor');
                    if (allIcons) allIcons.forEach(function(el) { el.classList.remove('active'); });
                    var cBtn = _tvScopedById(chartId, 'tvchart-tool-cursor');
                    if (cBtn) cBtn.classList.add('active');
                    return;
                }

                // Activate the selected drawing tool
                _tvSetDrawTool(chartId, toolName);
            });
        });

        // Tool-group flyout — clicking a group button:
        //   • If NOT already active → select last-used tool from that group
        //   • If already active → open flyout to switch sub-tool
        if (!window.__PYWRY_TVCHART_DOC_HANDLERS_FLYOUT__) {
        window.__PYWRY_TVCHART_DOC_HANDLERS_FLYOUT__ = true;
        document.addEventListener('click', function(e) {
            // Ignore clicks that originated from within a flyout item —
            // the flyout's own mousedown handler already processed the selection
            // and removed the flyout from the DOM.
            if (e.target.closest('.pywry-tool-flyout-item') || e.target.closest('.pywry-tool-flyout')) {
                return;
            }
            var groupBtn = e.target.closest('.pywry-tool-group');
            if (groupBtn) {
                e.stopPropagation();
                var chartId = _tvResolveChartIdFromElement(groupBtn);
                if (groupBtn.classList.contains('active')) {
                    _tvShowToolGroupFlyout(groupBtn);
                } else {
                    _tvHideToolGroupFlyout();
                    var groupName = groupBtn.getAttribute('data-tool-group');
                    var toolId = _toolGroupActive[groupName];

                    var allIcons = _tvScopedQueryAll(chartId, '.pywry-toolbar-left .pywry-icon-btn');
                    if (allIcons) allIcons.forEach(function(el) { el.classList.remove('active'); });
                    groupBtn.classList.add('active');

                    _tvSetDrawTool(chartId, toolId);
                }
                return;
            }
            // Click outside closes the flyout
            if (_activeGroupFlyout && !e.target.closest('.pywry-tool-flyout')) {
                _tvHideToolGroupFlyout();
            }
        }, true);
        } // end __PYWRY_TVCHART_DOC_HANDLERS_FLYOUT__ guard
    }

    // Expose globally so the widget render function can call it with
    // an explicit bridge argument (in ESM/anywidget context).
    window._tvRegisterEventHandlers = onReady;

    // Register when ready (native window flow where window.pywry exists).
    // In widget mode, window.pywry is never set — registration happens
    // via the explicit _tvRegisterEventHandlers(bridge) call instead.
    if (window.pywry) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() { onReady(window.pywry); });
        } else {
            onReady(window.pywry);
        }
    }
})();
