function _tvDatafeedNextRequestId(prefix) {
    var df = window.__PYWRY_TVCHART_DATAFEED__;
    df.seq = (df.seq || 0) + 1;
    return (prefix || 'req') + '-' + String(df.seq);
}

function _tvRequestDatafeedSearch(chartId, query, limit, callback, exchange, symbolType) {
    var _bridge = _tvGetBridge(chartId);
    if (!_bridge) {
        callback({ items: [], error: 'pywry bridge unavailable' });
        return null;
    }
    var requestId = _tvDatafeedNextRequestId('search');
    window.__PYWRY_TVCHART_DATAFEED__.pendingSearch[requestId] = callback;
    _bridge.emit('tvchart:datafeed-search-request', {
        chartId: chartId,
        requestId: requestId,
        query: String(query || ''),
        exchange: String(exchange || ''),
        symbolType: String(symbolType || ''),
        limit: typeof limit === 'number' ? limit : 20,
    });
    return requestId;
}

function _tvRequestDatafeedResolve(chartId, symbol, callback) {
    var _bridge = _tvGetBridge(chartId);
    if (!_bridge) {
        callback({ symbolInfo: null, error: 'pywry bridge unavailable' });
        return null;
    }
    var requestId = _tvDatafeedNextRequestId('resolve');
    window.__PYWRY_TVCHART_DATAFEED__.pendingResolve[requestId] = callback;
    _bridge.emit('tvchart:datafeed-resolve-request', {
        chartId: chartId,
        requestId: requestId,
        symbol: String(symbol || ''),
    });
    return requestId;
}

/**
 * Request datafeed configuration (onReady).
 * The Python backend responds with tvchart:datafeed-config-response.
 */
function _tvRequestDatafeedConfig(chartId, callback) {
    var _bridge = _tvGetBridge(chartId);
    if (!_bridge) {
        callback({ config: {}, error: 'pywry bridge unavailable' });
        return null;
    }
    var requestId = _tvDatafeedNextRequestId('config');
    window.__PYWRY_TVCHART_DATAFEED__.pendingConfig[requestId] = callback;
    _bridge.emit('tvchart:datafeed-config-request', {
        chartId: chartId,
        requestId: requestId,
    });
    return requestId;
}

/**
 * Request historical bars (getBars).
 * The Python backend responds with tvchart:datafeed-history-response.
 */
function _tvRequestDatafeedHistory(chartId, symbolInfo, resolution, periodParams, callback) {
    var _bridge = _tvGetBridge(chartId);
    if (!_bridge) {
        callback({ bars: [], status: 'error', error: 'pywry bridge unavailable' });
        return null;
    }
    var requestId = _tvDatafeedNextRequestId('history');
    window.__PYWRY_TVCHART_DATAFEED__.pendingHistory[requestId] = callback;
    var symbol = (symbolInfo && (symbolInfo.ticker || symbolInfo.name || symbolInfo.symbol)) || '';
    var payload = {
        chartId: chartId,
        requestId: requestId,
        symbol: String(symbol),
        resolution: String(resolution || ''),
        from: periodParams.from || 0,
        to: periodParams.to || 0,
        firstDataRequest: !!periodParams.firstDataRequest,
    };
    // Only include countBack when actually provided (UDF spec: when set, 'from' is ignored)
    if (periodParams.countBack != null && periodParams.countBack > 0) {
        payload.countBack = periodParams.countBack;
    }
    _bridge.emit('tvchart:datafeed-history-request', payload);
    return requestId;
}

/**
 * Subscribe to real-time bar updates (subscribeBars).
 * The Python backend pushes updates via tvchart:datafeed-bar-update.
 */

// ---------------------------------------------------------------------------
// Scrollback: auto-load older bars when the user scrolls near the left edge
// ---------------------------------------------------------------------------

var _TV_SCROLLBACK_THRESHOLD = 10;   // logical bars from the left edge
var _TV_SCROLLBACK_COUNT     = 300;  // bars to request per fetch

/**
 * Wire up scrollback for a chart+series after initial bars are loaded.
 *
 * Listens to logical range changes; when the left edge comes within
 * _TV_SCROLLBACK_THRESHOLD bars of index 0, it fires a history request
 * for older data and prepends it.
 */
function _tvWireScrollback(entry, sid, series, symbolInfo, resolution, sType) {
    var chartId = entry.chartId;
    var loading = false;
    var exhausted = false;

    entry.chart.timeScale().subscribeVisibleLogicalRangeChange(function(range) {
        if (!range || loading || exhausted) return;
        // Only fire when user scrolls near the left edge
        if (range.from > _TV_SCROLLBACK_THRESHOLD) return;
        // Once the user has dragged past the data into pure empty space
        // (range.from negative beyond the threshold), stop firing — the
        // first request already came back NO_DATA so further scrolling
        // shouldn't keep asking.  The `exhausted` flag normally catches
        // this, but this guard cuts off any pre-exhaustion overshoot
        // where the user yanks the scroll wheel hard.
        if (range.from < -_TV_SCROLLBACK_THRESHOLD * 4) return;

        // Find the oldest bar currently loaded
        var raw = entry._seriesRawData[sid];
        if (!raw || raw.length === 0) return;
        var oldestTime = raw[0].time;
        if (typeof oldestTime !== 'number' || oldestTime <= 0) return;

        loading = true;
        var periodParams = {
            from: 0,
            to: oldestTime - 1,
            countBack: _TV_SCROLLBACK_COUNT,
            firstDataRequest: false,
        };

        _tvRequestDatafeedHistory(chartId, symbolInfo, resolution, periodParams, function(resp) {
            loading = false;
            // Treat any non-success outcome as exhaustion so the
            // visible-range-change handler stops retrying — otherwise
            // every scroll-tick fires another fetch and overloads the
            // bridge.  This includes:
            //   - missing/error response (transport failure)
            //   - explicit noData / status:"no_data"
            //   - empty bars array (UDF "no more history" signal)
            if (!resp || resp.error
                    || (resp.noData != null && resp.noData)
                    || resp.status === 'no_data'
                    || resp.status === 'error') {
                exhausted = true;
                return;
            }
            var bars = resp.bars || [];
            if (bars.length === 0) {
                exhausted = true;
                return;
            }
            // Server returned bars whose newest timestamp is at or after
            // our current oldest — no actual older data was added, so
            // continuing to ask would loop forever requesting the same
            // window.  Stop.
            var newestNew = bars[bars.length - 1] && bars[bars.length - 1].time;
            if (typeof newestNew === 'number' && newestNew >= oldestTime) {
                exhausted = true;
                return;
            }

            // Prepend older bars to the existing data
            var normalized = _tvNormalizeBarsForSeriesType(bars, sType);
            if (normalized.length === 0) { exhausted = true; return; }

            var merged = normalized.concat(raw);
            entry._seriesRawData[sid] = merged;

            // Update canonical raw data for indicator computation
            if (_tvLooksLikeOhlcBars(bars)) {
                var canonical = entry._seriesCanonicalRawData[sid] || [];
                entry._seriesCanonicalRawData[sid] = bars.concat(canonical);
            }
            if (sid === 'main') {
                entry._rawData = merged;
            }

            // Prepend volume bars if present
            var volData = null;
            if (entry.volumeMap[sid]) {
                volData = _tvExtractVolumeFromBars(bars, entry.theme || _tvDetectTheme(), entry);
                if (volData && volData.length > 0) {
                    var existingVol = entry._seriesRawData['volume'] || [];
                    var mergedVol = volData.concat(existingVol);
                    entry._seriesRawData['volume'] = mergedVol;
                }
            }

            // When RTH filter is active, push the merged bars through
            // the session filter so both the main series and every
            // indicator see the refreshed set.  Pass skipFitContent so
            // the user's scroll position is preserved AND we don't
            // retrigger the scrollback handler in an infinite loop.
            if (entry._sessionMode === 'RTH' && typeof _tvApplySessionFilter === 'function') {
                _tvApplySessionFilter({ skipFitContent: true });
            } else {
                series.setData(merged);
                if (entry.volumeMap[sid] && volData && volData.length > 0) {
                    entry.volumeMap[sid].setData(entry._seriesRawData['volume']);
                }
                if (typeof _tvRecomputeIndicatorsForChart === 'function') {
                    try { _tvRecomputeIndicatorsForChart(chartId, sid); } catch (_e) {}
                }
                if (typeof _tvRefreshVisibleVolumeProfiles === 'function') {
                    try { _tvRefreshVisibleVolumeProfiles(chartId); } catch (_e2) {}
                }
            }
        });
    });
}

function _tvDatafeedSubscribeBars(chartId, symbolInfo, resolution, onTick, listenerGuid, onResetCacheNeeded) {
    var df = window.__PYWRY_TVCHART_DATAFEED__;
    df.subscriptions[listenerGuid] = {
        onTick: onTick,
        onResetCacheNeeded: onResetCacheNeeded,
        symbolInfo: symbolInfo,
        resolution: resolution,
        chartId: chartId,
    };
    var _bridge = _tvGetBridge(chartId);
    if (_bridge) {
        var symbol = (symbolInfo && (symbolInfo.ticker || symbolInfo.name || symbolInfo.symbol)) || '';
        _bridge.emit('tvchart:datafeed-subscribe', {
            chartId: chartId,
            listenerGuid: listenerGuid,
            symbol: String(symbol),
            resolution: String(resolution || ''),
        });
    }
}

/**
 * Unsubscribe from real-time bar updates (unsubscribeBars).
 */
function _tvDatafeedUnsubscribeBars(listenerGuid) {
    var df = window.__PYWRY_TVCHART_DATAFEED__;
    var sub = df.subscriptions[listenerGuid];
    delete df.subscriptions[listenerGuid];
    var _bridge = _tvGetBridge(sub ? sub.chartId : undefined);
    if (_bridge) {
        _bridge.emit('tvchart:datafeed-unsubscribe', {
            listenerGuid: listenerGuid,
            chartId: sub ? sub.chartId : undefined,
        });
    }
}

/**
 * Request chart marks for visible bar range (getMarks).
 * Only called if DatafeedConfiguration.supports_marks is true.
 */
function _tvRequestDatafeedMarks(chartId, symbolInfo, from, to, resolution, callback) {
    var _bridge = _tvGetBridge(chartId);
    if (!_bridge) {
        callback([]);
        return null;
    }
    var requestId = _tvDatafeedNextRequestId('marks');
    window.__PYWRY_TVCHART_DATAFEED__.pendingMarks[requestId] = callback;
    var symbol = (symbolInfo && (symbolInfo.ticker || symbolInfo.name || symbolInfo.symbol)) || '';
    _bridge.emit('tvchart:datafeed-marks-request', {
        chartId: chartId,
        requestId: requestId,
        symbol: String(symbol),
        from: from,
        to: to,
        resolution: String(resolution || ''),
    });
    return requestId;
}

/**
 * Request timescale marks for visible bar range (getTimescaleMarks).
 * Only called if DatafeedConfiguration.supports_timescale_marks is true.
 */
function _tvRequestDatafeedTimescaleMarks(chartId, symbolInfo, from, to, resolution, callback) {
    var _bridge = _tvGetBridge(chartId);
    if (!_bridge) {
        callback([]);
        return null;
    }
    var requestId = _tvDatafeedNextRequestId('tsmarks');
    window.__PYWRY_TVCHART_DATAFEED__.pendingTimescaleMarks[requestId] = callback;
    var symbol = (symbolInfo && (symbolInfo.ticker || symbolInfo.name || symbolInfo.symbol)) || '';
    _bridge.emit('tvchart:datafeed-timescale-marks-request', {
        chartId: chartId,
        requestId: requestId,
        symbol: String(symbol),
        from: from,
        to: to,
        resolution: String(resolution || ''),
    });
    return requestId;
}

/**
 * Request server time (getServerTime).
 * Only called if DatafeedConfiguration.supports_time is true.
 */
function _tvRequestDatafeedServerTime(chartId, callback) {
    var _bridge = _tvGetBridge(chartId);
    if (!_bridge) {
        callback(Math.floor(Date.now() / 1000));
        return null;
    }
    var requestId = _tvDatafeedNextRequestId('time');
    window.__PYWRY_TVCHART_DATAFEED__.pendingServerTime[requestId] = callback;
    _bridge.emit('tvchart:datafeed-server-time-request', {
        chartId: chartId,
        requestId: requestId,
    });
    return requestId;
}

/**
 * Normalize a raw symbol info object from the Python backend into the
 * full LibrarySymbolInfo shape expected by the TradingView Charting Library.
 *
 * This function maps both camelCase (JS) and snake_case (Python) property names
 * so that data from either convention is correctly resolved.
 */
function _tvNormalizeSymbolInfoFull(item) {
    if (!item || typeof item !== 'object') return null;

    // --- Required fields ---
    var name = String(item.name || item.symbol || item.ticker || '').trim();
    if (!name) return null;

    var ticker = item.ticker != null ? String(item.ticker).trim() : name;
    var description = String(item.description || '').trim();
    var exchange = String(item.exchange || item.listed_exchange || item.listedExchange || '').trim();
    var listedExchange = String(item.listed_exchange || item.listedExchange || exchange).trim();
    var type = String(item.type || item.symbol_type || item.symbolType || 'stock').trim();
    var session = String(item.session || '24x7').trim();
    var tz = String(item.timezone || 'Etc/UTC').trim();
    var minmov = typeof item.minmov === 'number' ? item.minmov : 1;
    var pricescale = typeof item.pricescale === 'number' ? item.pricescale : 100;
    var format = String(item.format || 'price').trim();

    var result = {
        name: name,
        ticker: ticker,
        description: description,
        exchange: exchange,
        listed_exchange: listedExchange,
        type: type,
        session: session,
        timezone: tz,
        minmov: minmov,
        pricescale: pricescale,
        format: format,
    };

    // --- Symbol identification helpers ---
    if (item.full_name || item.fullName) result.full_name = String(item.full_name || item.fullName);
    if (item.base_name || item.baseName) result.base_name = item.base_name || item.baseName;

    // --- Currency & unit ---
    if (item.currency_code || item.currencyCode) result.currency_code = String(item.currency_code || item.currencyCode);
    if (item.original_currency_code || item.originalCurrencyCode) result.original_currency_code = String(item.original_currency_code || item.originalCurrencyCode);
    if (item.unit_id || item.unitId) result.unit_id = String(item.unit_id || item.unitId);
    if (item.original_unit_id || item.originalUnitId) result.original_unit_id = String(item.original_unit_id || item.originalUnitId);
    if (item.unit_conversion_types || item.unitConversionTypes) result.unit_conversion_types = item.unit_conversion_types || item.unitConversionTypes;

    // --- Resolution support ---
    var boolOpts = [
        ['has_intraday', 'hasIntraday'],
        ['has_daily', 'hasDaily'],
        ['has_weekly_and_monthly', 'hasWeeklyAndMonthly'],
        ['has_seconds', 'hasSeconds'],
        ['has_ticks', 'hasTicks'],
        ['has_empty_bars', 'hasEmptyBars'],
        ['build_seconds_from_ticks', 'buildSecondsFromTicks'],
        ['fractional', 'fractional'],
        ['expired', 'expired'],
    ];
    for (var bi = 0; bi < boolOpts.length; bi++) {
        var snake = boolOpts[bi][0], camel = boolOpts[bi][1];
        if (item[snake] != null) result[snake] = !!item[snake];
        else if (item[camel] != null) result[snake] = !!item[camel];
    }

    var arrOpts = [
        ['supported_resolutions', 'supportedResolutions'],
        ['intraday_multipliers', 'intradayMultipliers'],
        ['seconds_multipliers', 'secondsMultipliers'],
        ['daily_multipliers', 'dailyMultipliers'],
        ['weekly_multipliers', 'weeklyMultipliers'],
        ['monthly_multipliers', 'monthlyMultipliers'],
    ];
    for (var ai = 0; ai < arrOpts.length; ai++) {
        var sn = arrOpts[ai][0], cm = arrOpts[ai][1];
        if (item[sn] != null) result[sn] = item[sn];
        else if (item[cm] != null) result[sn] = item[cm];
    }

    // --- Display ---
    var strOpts = [
        ['visible_plots_set', 'visiblePlotsSet'],
        ['data_status', 'dataStatus'],
        ['long_description', 'longDescription'],
        ['exchange_logo', 'exchangeLogo'],
        ['sector', 'sector'],
        ['industry', 'industry'],
        ['session_display', 'sessionDisplay'],
        ['session_holidays', 'sessionHolidays'],
        ['session_premarket', 'sessionPremarket'],
        ['session_regular', 'sessionRegular'],
        ['session_postmarket', 'sessionPostmarket'],
        ['session_overnight', 'sessionOvernight'],
        ['corrections', 'corrections'],
        ['subsession_id', 'subsessionId'],
        ['variable_tick_size', 'variableTickSize'],
        ['price_source_id', 'priceSourceId'],
    ];
    for (var si = 0; si < strOpts.length; si++) {
        var sk = strOpts[si][0], ck = strOpts[si][1];
        if (item[sk] != null) result[sk] = item[sk];
        else if (item[ck] != null) result[sk] = item[ck];
    }

    var numOpts = [
        ['volume_precision', 'volumePrecision'],
        ['delay', 'delay'],
        ['minmove2', 'minmove2'],
        ['expiration_date', 'expirationDate'],
    ];
    for (var ni = 0; ni < numOpts.length; ni++) {
        var nk = numOpts[ni][0], nc = numOpts[ni][1];
        if (item[nk] != null) result[nk] = item[nk];
        else if (item[nc] != null) result[nk] = item[nc];
    }

    // --- Complex objects ---
    if (item.logo_urls || item.logoUrls) result.logo_urls = item.logo_urls || item.logoUrls;
    if (item.subsessions) result.subsessions = item.subsessions;
    if (item.price_sources || item.priceSources) result.price_sources = item.price_sources || item.priceSources;
    if (item.library_custom_fields || item.libraryCustomFields) result.library_custom_fields = item.library_custom_fields || item.libraryCustomFields;
    if (item.session_schedule) result.session_schedule = item.session_schedule;

    // --- Compat: displaySymbol / requestSymbol for internal use ---
    result.displaySymbol = (ticker || name).toUpperCase();
    result.requestSymbol = ticker || name;

    return result;
}

/**
 * Build a complete TradingView-compatible Datafeed object for a chart instance.
 *
 * This implements IExternalDatafeed + IDatafeedChartApi.
 * The datafeed proxies all calls through the PyWry event bridge to the
 * Python backend, which handles actual data retrieval.
 *
 * @param {string} chartId - Chart instance ID for routing events.
 * @param {object} [overrides] - Optional DatafeedConfiguration defaults.
 * @returns {object} A TradingView-compatible Datafeed object.
 */
function _tvCreateDatafeed(chartId, overrides) {
    var _config = overrides || {};

    return {
        /**
         * IExternalDatafeed.onReady
         * Called by the library to get DatafeedConfiguration.
         */
        onReady: function(callback) {
            // Per spec, callback must be called asynchronously
            setTimeout(function() {
                _tvRequestDatafeedConfig(chartId, function(resp) {
                    var cfg = (resp && resp.config) ? resp.config : _config;
                    callback(cfg);
                });
            }, 0);
        },

        /**
         * IDatafeedChartApi.searchSymbols
         */
        searchSymbols: function(userInput, exchange, symbolType, onResult) {
            if (!window.pywry) {
                onResult([]);
                return;
            }
            var requestId = _tvDatafeedNextRequestId('search');
            window.__PYWRY_TVCHART_DATAFEED__.pendingSearch[requestId] = function(resp) {
                var items = (resp && resp.items) || [];
                var normalized = [];
                for (var i = 0; i < items.length; i++) {
                    var raw = items[i];
                    normalized.push({
                        symbol: String(raw.symbol || raw.ticker || ''),
                        full_name: String(raw.full_name || raw.fullName || raw.symbol || ''),
                        description: String(raw.description || ''),
                        exchange: String(raw.exchange || ''),
                        type: String(raw.type || raw.symbol_type || raw.symbolType || ''),
                        ticker: raw.ticker || raw.symbol || '',
                        logo_urls: raw.logo_urls || raw.logoUrls || undefined,
                        exchange_logo: raw.exchange_logo || raw.exchangeLogo || undefined,
                    });
                }
                onResult(normalized);
            };
            window.pywry.emit('tvchart:datafeed-search-request', {
                chartId: chartId,
                requestId: requestId,
                query: String(userInput || ''),
                exchange: String(exchange || ''),
                symbolType: String(symbolType || ''),
                limit: 30,
            });
        },

        /**
         * IDatafeedChartApi.resolveSymbol
         */
        resolveSymbol: function(symbolName, onResolve, onError, extension) {
            _tvRequestDatafeedResolve(chartId, symbolName, function(resp) {
                if (resp && resp.error) {
                    if (onError) onError(resp.error);
                    return;
                }
                var raw = resp && (resp.symbolInfo || resp.symbol_info);
                var info = _tvNormalizeSymbolInfoFull(raw);
                if (!info) {
                    if (onError) onError('Symbol not found: ' + symbolName);
                    return;
                }
                onResolve(info);
            });
        },

        /**
         * IDatafeedChartApi.getBars
         */
        getBars: function(symbolInfo, resolution, periodParams, onResult, onError) {
            _tvRequestDatafeedHistory(chartId, symbolInfo, resolution, periodParams, function(resp) {
                if (resp && resp.error) {
                    if (onError) onError(resp.error);
                    return;
                }
                var bars = (resp && resp.bars) || [];
                var meta = {};
                if (resp) {
                    if (resp.noData != null) meta.noData = !!resp.noData;
                    else if (resp.status === 'no_data') meta.noData = true;
                    if (resp.nextTime != null) meta.nextTime = resp.nextTime;
                }
                onResult(bars, meta);
            });
        },

        /**
         * IDatafeedChartApi.subscribeBars
         */
        subscribeBars: function(symbolInfo, resolution, onTick, listenerGuid, onResetCacheNeeded) {
            _tvDatafeedSubscribeBars(chartId, symbolInfo, resolution, onTick, listenerGuid, onResetCacheNeeded);
        },

        /**
         * IDatafeedChartApi.unsubscribeBars
         */
        unsubscribeBars: function(listenerGuid) {
            _tvDatafeedUnsubscribeBars(listenerGuid);
        },

        /**
         * IDatafeedChartApi.getMarks (optional)
         */
        getMarks: function(symbolInfo, from, to, onDataCallback, resolution) {
            _tvRequestDatafeedMarks(chartId, symbolInfo, from, to, resolution, onDataCallback);
        },

        /**
         * IDatafeedChartApi.getTimescaleMarks (optional)
         */
        getTimescaleMarks: function(symbolInfo, from, to, onDataCallback, resolution) {
            _tvRequestDatafeedTimescaleMarks(chartId, symbolInfo, from, to, resolution, onDataCallback);
        },

        /**
         * IDatafeedChartApi.getServerTime (optional)
         */
        getServerTime: function(callback) {
            _tvRequestDatafeedServerTime(chartId, callback);
        },

        /**
         * IDatafeedChartApi.getVolumeProfileResolutionForPeriod (optional)
         * Default implementation returns currentResolution per spec.
         */
        getVolumeProfileResolutionForPeriod: function(currentResolution) {
            return currentResolution;
        },
    };
}

// ---------------------------------------------------------------------------
// Datafeed mode orchestrator — async init: onReady → resolve → getBars → subscribe
// ---------------------------------------------------------------------------

/**
 * Initialize a chart in datafeed mode.  Series are populated asynchronously
 * via the onReady → resolveSymbol → getBars → subscribeBars chain.
 *
 * @param {Object} entry - The chart registry entry (already stored in __PYWRY_TVCHARTS__)
 * @param {Array}  seriesList - Array of series descriptors with symbol/resolution
 * @param {string} theme - 'dark' | 'light'
 */
function _tvInitDatafeedMode(entry, seriesList, theme) {
    var chartId = entry.chartId;
    var chart = entry.chart;
    var datafeed = _tvCreateDatafeed(chartId);
    entry.datafeed = datafeed;

    datafeed.onReady(function(config) {
        entry._datafeedConfig = config;

        var pending = seriesList.length;
        if (pending === 0) {
            chart.timeScale().fitContent();
            _tvRenderHoverLegend(chartId, null);
            return;
        }

        for (var i = 0; i < seriesList.length; i++) {
            (function(idx) {
                var s = seriesList[idx];
                var symbolName = s.symbol || 'UNKNOWN';
                var resolution = s.resolution || '1D';
                var sid = s.seriesId || ('series-' + idx);

                datafeed.resolveSymbol(symbolName, function(symbolInfo) {
                    var sType = s.seriesType || 'Candlestick';
                    var sOptions = _tvBuildSeriesOptions(s.seriesOptions || {}, sType, theme);

                    // Start exchange clock on bottom toolbar
                    if (idx === 0 && symbolInfo && symbolInfo.timezone) {
                        (function(tz) {
                            var clockEl = document.getElementById('tvchart-exchange-clock');
                            if (clockEl) {
                                function updateClock() {
                                    try {
                                        var now = new Date();
                                        var timeStr = now.toLocaleString('en-US', {
                                            timeZone: tz,
                                            hour: '2-digit', minute: '2-digit', second: '2-digit',
                                            hour12: false,
                                        });
                                        var offsetParts = now.toLocaleString('en-US', {
                                            timeZone: tz, timeZoneName: 'shortOffset',
                                        }).split(' ');
                                        var utcOffset = offsetParts[offsetParts.length - 1] || '';
                                        clockEl.textContent = timeStr + ' (' + utcOffset + ')';
                                    } catch(e) { clockEl.textContent = ''; }
                                }
                                updateClock();
                                if (entry._clockInterval) clearInterval(entry._clockInterval);
                                entry._clockInterval = setInterval(updateClock, 1000);
                            }
                        })(symbolInfo.timezone);
                    }

                    // Update legend title with resolved symbol info
                    if (idx === 0 && symbolInfo) {
                        var resolvedTitle = String(symbolInfo.ticker || symbolInfo.name || symbolName).toUpperCase();
                        var legendBox = _tvScopedById(chartId, 'tvchart-legend-box');
                        if (legendBox) {
                            legendBox.dataset.baseTitle = resolvedTitle;
                            _tvRefreshLegendTitle(chartId);
                        }
                    }

                    // Apply exchange timezone to the chart time axis
                    if (idx === 0 && symbolInfo && symbolInfo.timezone && symbolInfo.timezone !== 'Etc/UTC') {
                        // Track current resolution so formatters know whether to show time
                        entry._currentResolution = resolution;

                        var _isDaily = function() {
                            var r = entry._currentResolution || '';
                            return /^[1-9]?[DWM]$/.test(r) || /^\d+[DWM]$/.test(r);
                        };
                        var _isoDate = function(d, tz) {
                            var y = d.toLocaleString('en-US', { timeZone: tz, year: 'numeric' });
                            var m = d.toLocaleString('en-US', { timeZone: tz, month: '2-digit' });
                            var day = d.toLocaleString('en-US', { timeZone: tz, day: '2-digit' });
                            return y + '-' + m + '-' + day;
                        };

                        try {
                            chart.applyOptions({
                                localization: {
                                    timeFormatter: function(ts) {
                                        var ms = (typeof ts === 'number' && ts < 1e12) ? ts * 1000 : ts;
                                        var d = new Date(ms);
                                        if (_isDaily()) {
                                            return _isoDate(d, symbolInfo.timezone);
                                        }
                                        return _isoDate(d, symbolInfo.timezone) + ' ' + d.toLocaleString('en-US', {
                                            timeZone: symbolInfo.timezone,
                                            hour: '2-digit', minute: '2-digit', hour12: false,
                                        });
                                    },
                                },
                                timeScale: {
                                    timeVisible: !_isDaily(),
                                    tickMarkFormatter: function(time, tickType, locale) {
                                        var ms = (typeof time === 'number' && time < 1e12) ? time * 1000 : time;
                                        var d = new Date(ms);
                                        var tz = symbolInfo.timezone;
                                        // TickMarkType: 0=Year, 1=Month, 2=DayOfMonth, 3=Time, 4=TimeWithSeconds
                                        if (tickType === 0) {
                                            return d.toLocaleString('en-US', { timeZone: tz, year: 'numeric' });
                                        }
                                        if (tickType === 1) {
                                            return d.toLocaleString('en-US', { timeZone: tz, year: 'numeric', month: 'short' });
                                        }
                                        if (tickType === 2 || _isDaily()) {
                                            return d.toLocaleString('en-US', { timeZone: tz, month: 'short', day: 'numeric' });
                                        }
                                        return d.toLocaleString('en-US', {
                                            timeZone: tz, hour: '2-digit', minute: '2-digit', hour12: false,
                                        });
                                    },
                                },
                            });
                        } catch (tzErr) {
                            if (typeof console !== 'undefined') console.warn('[PyWry TVChart] timezone apply error:', tzErr);
                        }
                    }

                    // Overlay series get separate price scales
                    if (idx > 0) {
                        sOptions.priceScaleId = sid;
                        _tvRegisterCustomPriceScaleId(entry, sOptions.priceScaleId);
                        if (!sOptions.priceFormat) {
                            sOptions.priceFormat = { type: 'price', precision: 2, minMove: 0.01 };
                        }
                    }

                    var series = _tvAddSeriesCompat(chart, sType, sOptions);
                    entry.seriesMap[sid] = series;
                    entry._resolvedSymbolInfo = entry._resolvedSymbolInfo || {};
                    entry._resolvedSymbolInfo[sid] = symbolInfo;
                    entry._legendSeriesColors[sid] = (
                        sOptions.color || sOptions.lineColor ||
                        sOptions.upColor || sOptions.borderUpColor || '#4c87ff'
                    );
                    // `whenMainSeriesReady` must guarantee bars are loaded,
                    // not just the series constructed.  Fire happens inside
                    // `_onBarsLoaded` below, after setData + `_seriesRawData`
                    // — otherwise indicator re-add after an interval/symbol
                    // change computes from an empty bar set and silently
                    // produces nothing.

                    // Request initial historical bars
                    var periodParams = {
                        from: 0,
                        to: Math.floor(Date.now() / 1000),
                        countBack: 300,
                        firstDataRequest: true,
                    };

                    // When bars are pre-fetched by Python (via tvchart:data-response
                    // after an interval change), use them directly to avoid a
                    // redundant round-trip to the backend.
                    var _preFetchedBars = (s.bars && s.bars.length > 0) ? s.bars : null;

                    var _onBarsLoaded = function(bars, meta) {
                        var normalizedBars = _tvNormalizeBarsForSeriesType(bars, sType);
                        series.setData(normalizedBars);
                        entry._seriesRawData[sid] = normalizedBars;

                        // Main series now has data — fire any pending
                        // whenMainSeriesReady callbacks.  Callers waiting on
                        // this event need `_seriesRawData[sid]` populated
                        // (e.g., indicator re-add after interval change).
                        if (_tvIsMainSeriesId(sid) || sid === 'series-0') {
                            _tvFireMainSeriesReady(entry);
                        }

                        // Ensure payload.interval is set so the data-response
                        // handler can compare intervals correctly on the first
                        // symbol-change request (prevents unnecessary recreate).
                        if (idx === 0 && entry.payload && !entry.payload.interval) {
                            entry.payload.interval = resolution;
                        }

                        if (_tvLooksLikeOhlcBars(bars)) {
                            entry._seriesCanonicalRawData[sid] = bars;
                        }

                        // Baseline base value from actual data
                        if (sType === 'Baseline' && normalizedBars.length > 0) {
                            var baseVal = _tvComputeBaselineValue(normalizedBars, 50);
                            series.applyOptions({
                                baseValue: { type: 'price', price: baseVal, _level: 50 },
                            });
                        }

                        // Store raw data for indicator computation (main series)
                        if (idx === 0 && bars.length > 0) {
                            entry._rawData = _tvLooksLikeOhlcBars(bars) ? bars : normalizedBars;
                        }

                        // Wire scrollback: auto-load older bars on scroll
                        _tvWireScrollback(entry, sid, series, symbolInfo, resolution, sType);

                        // Auto-enable volume from OHLCV bars (with per-bar up/down colors)
                        var volumeData = _tvExtractVolumeFromBars(bars, theme, entry);
                        if (volumeData && volumeData.length > 0) {
                            var volOptions = _tvBuildVolumeOptions(s, theme);
                            _tvRegisterCustomPriceScaleId(entry, volOptions.priceScaleId);
                            var vPaneIndex = _tvReserveVolumePane(entry, sid);
                            var volSeries = _tvAddSeriesCompat(chart, 'Histogram', volOptions, vPaneIndex);
                            volSeries.setData(volumeData);
                            entry.volumeMap[sid] = volSeries;
                            // Store volume raw data for legend rendering
                            entry._seriesRawData['volume'] = volumeData;
                            // Update legend dataset to reflect volume is available
                            var _legBox = _tvScopedById(chartId, 'tvchart-legend-box');
                            if (_legBox) _legBox.dataset.showVolume = '1';
                            if (sid === 'main') {
                                _tvApplyDefaultVolumePaneHeight(entry, vPaneIndex);
                                _tvEnforceMainScaleDividerClearance(entry, 0.1, 0.08);
                            }
                            // Notify legend that volume is now available
                            try {
                                window.dispatchEvent(new CustomEvent('pywry:legend-refresh', { detail: { chartId: chartId } }));
                            } catch (_e) {}
                        }

                        // Subscribe for real-time bar updates
                        var guid = chartId + '_' + sid + '_' + resolution;
                        entry._datafeedSubscriptions = entry._datafeedSubscriptions || {};
                        entry._datafeedSubscriptions[sid] = guid;

                        datafeed.subscribeBars(symbolInfo, resolution, function(bar) {
                            // Skip bars outside the regular session when RTH
                            // is active.  Prefer the session-string check
                            // (works for every datafeed) and fall back to the
                            // per-bar market_hours field when present.
                            if (entry._sessionMode === 'RTH') {
                                if (typeof _tvIsBarInCurrentSession === 'function'
                                        && !_tvIsBarInCurrentSession(bar.time)) {
                                    return;
                                }
                                if (bar.market_hours != null && bar.market_hours !== 2) {
                                    return;
                                }
                            }
                            var normalized = _tvNormalizeBarsForSeriesType([bar], sType);
                            if (normalized.length > 0) {
                                series.update(normalized[0]);
                            }
                            if (bar.volume != null && entry.volumeMap[sid]) {
                                var palette = TVCHART_THEMES._get(entry.theme || _tvDetectTheme());
                                var prefs = entry._volumeColorPrefs || {};
                                var isUp;
                                if (prefs.colorBasedOnPrevClose) {
                                    var rawBars = entry._rawData || entry._seriesRawData && entry._seriesRawData[sid];
                                    var prevClose = null;
                                    if (rawBars && rawBars.length > 1) {
                                        var prev = rawBars[rawBars.length - 2];
                                        prevClose = prev ? (prev.close != null ? prev.close : prev.Close) : null;
                                    }
                                    isUp = (prevClose != null && bar.close != null) ? bar.close >= prevClose : true;
                                } else {
                                    isUp = (bar.close != null && bar.open != null) ? bar.close >= bar.open : true;
                                }
                                var uc = prefs.upColor || palette.volumeUp;
                                var dc = prefs.downColor || palette.volumeDown || palette.volumeUp;
                                entry.volumeMap[sid].update({
                                    time: bar.time,
                                    value: bar.volume,
                                    color: isUp ? uc : dc,
                                });
                            }
                        }, guid, function() {
                            // onResetCacheNeeded — re-fetch all bars
                            datafeed.getBars(symbolInfo, resolution, periodParams, function(newBars) {
                                var nn = _tvNormalizeBarsForSeriesType(newBars, sType);
                                series.setData(nn);
                                entry._seriesRawData[sid] = nn;
                                // Refresh volume with per-bar colors
                                if (entry.volumeMap[sid]) {
                                    var vd = _tvExtractVolumeFromBars(newBars, entry.theme || _tvDetectTheme(), entry);
                                    if (vd && vd.length > 0) entry.volumeMap[sid].setData(vd);
                                }
                            }, function() {});
                        });

                        if (--pending === 0) {
                            // Apply RTH session filter if active
                            if (typeof _tvApplySessionFilter === 'function') {
                                _tvApplySessionFilter();
                            }
                            // Apply selected time-range tab, or fitContent as fallback
                            var sel = document.querySelector('.pywry-tab.pywry-tab-active[data-target-interval]');
                            var rangeApplied = false;
                            if (sel) {
                                var rangeVal = sel.getAttribute('data-value');
                                if (rangeVal && rangeVal !== 'all') {
                                    rangeApplied = _tvApplyTimeRangeSelection(entry, rangeVal);
                                }
                            }
                            if (!rangeApplied) chart.timeScale().fitContent();
                            _tvRenderHoverLegend(chartId, null);

                            // Apply deferred custom default settings now that series exist
                            if (entry._pendingCustomDefaults && typeof _tvApplySettingsToChart === 'function') {
                                _tvApplySettingsToChart(chartId, entry, entry._pendingCustomDefaults, { skipLocalization: true });
                                // Restore full-opacity theme background (settings apply
                                // uses 50% opacity which breaks fresh charts).
                                if (!entry._chartPrefs || !entry._chartPrefs.backgroundColor) {
                                    var _dfPalette = TVCHART_THEMES._get(entry.theme || 'dark');
                                    entry.chart.applyOptions({
                                        layout: {
                                            background: { type: LightweightCharts.ColorType.Solid, color: _dfPalette.background },
                                            textColor: _dfPalette.textColor,
                                        },
                                        grid: _dfPalette.grid,
                                        rightPriceScale: { borderColor: _dfPalette.grid.vertLines.color },
                                        timeScale: { borderColor: _dfPalette.grid.vertLines.color },
                                    });
                                }
                                delete entry._pendingCustomDefaults;
                            }
                        }
                    };

                    if (_preFetchedBars) {
                        _onBarsLoaded(_preFetchedBars, {});
                    } else {
                        datafeed.getBars(symbolInfo, resolution, periodParams, _onBarsLoaded, function(err) {
                            if (typeof console !== 'undefined') console.error('[PyWry TVChart] getBars error:', err);
                            if (--pending === 0) { chart.timeScale().fitContent(); }
                        });
                    }
                }, function(err) {
                    if (typeof console !== 'undefined') console.error('[PyWry TVChart] resolveSymbol error:', err);
                    if (--pending === 0) { chart.timeScale().fitContent(); }
                });
            })(i);
        }
    });
}
