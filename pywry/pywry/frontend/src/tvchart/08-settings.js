// ---------------------------------------------------------------------------
// Drawing Settings Panel (TV-style modal per drawing type)
// ---------------------------------------------------------------------------
var _settingsOverlay = null;
var _chartSettingsOverlay = null;
var _compareOverlay = null;
var _seriesSettingsOverlay = null;
var _volumeSettingsOverlay = null;
var _settingsOverlayChartId = null;
var _chartSettingsOverlayChartId = null;
var _compareOverlayChartId = null;
var _seriesSettingsOverlayChartId = null;
var _seriesSettingsOverlaySeriesId = null;
var _volumeSettingsOverlayChartId = null;

var _DRAW_TYPE_NAMES = {
    hline: 'Horizontal Line', trendline: 'Trend Line', rect: 'Rectangle',
    channel: 'Parallel Channel', fibonacci: 'Fibonacci Retracement',
    fib_extension: 'Trend-Based Fib Extension', fib_channel: 'Fib Channel',
    fib_timezone: 'Fib Time Zone', fib_fan: 'Fib Speed Resistance Fan',
    fib_arc: 'Fib Speed Resistance Arcs', fib_circle: 'Fib Circles',
    fib_wedge: 'Fib Wedge', pitchfan: 'Pitchfan',
    fib_time: 'Trend-Based Fib Time', fib_spiral: 'Fib Spiral',
    gann_box: 'Gann Box', gann_square_fixed: 'Gann Square Fixed',
    gann_square: 'Gann Square', gann_fan: 'Gann Fan',
    text: 'Text', measure: 'Measure', brush: 'Brush',
    ray: 'Ray', extended_line: 'Extended Line', hray: 'Horizontal Ray',
    vline: 'Vertical Line', crossline: 'Cross Line',
    flat_channel: 'Flat Top/Bottom', regression_channel: 'Regression Trend',
    highlighter: 'Highlighter',
    arrow_marker: 'Arrow Marker', arrow: 'Arrow',
    arrow_mark_up: 'Arrow Mark Up', arrow_mark_down: 'Arrow Mark Down',
    arrow_mark_left: 'Arrow Mark Left', arrow_mark_right: 'Arrow Mark Right',
    circle: 'Circle', ellipse: 'Ellipse', triangle: 'Triangle',
    rotated_rect: 'Rotated Rectangle', path: 'Path', polyline: 'Polyline',
    shape_arc: 'Arc', curve: 'Curve', double_curve: 'Double Curve',
    long_position: 'Long Position', short_position: 'Short Position',
    forecast: 'Forecast', bars_pattern: 'Bars Pattern',
    ghost_feed: 'Ghost Feed', projection: 'Projection',
    anchored_vwap: 'Anchored VWAP', fixed_range_vol: 'Fixed Range Volume Profile',
    price_range: 'Price Range', date_range: 'Date Range',
    date_price_range: 'Date and Price Range',
    anchored_text: 'Anchored Text', note: 'Note', price_note: 'Price Note',
    pin: 'Pin', callout: 'Callout', comment: 'Comment',
    price_label: 'Price Label', signpost: 'Signpost', flag_mark: 'Flag Mark'
};

var _LINE_STYLE_NAMES = ['Solid', 'Dashed', 'Dotted'];

function _tvInteractiveNavigationOptions() {
    return {
        handleScroll: {
            mouseWheel: true,
            pressedMouseMove: true,
            horzTouchDrag: true,
            vertTouchDrag: true,
        },
        handleScale: {
            mouseWheel: true,
            pinch: true,
            axisPressedMouseMove: {
                time: true,
                price: true,
            },
            axisDoubleClickReset: {
                time: true,
                price: true,
            },
        },
    };
}

function _tvLockedNavigationOptions() {
    return {
        handleScroll: {
            mouseWheel: false,
            pressedMouseMove: false,
            horzTouchDrag: false,
            vertTouchDrag: false,
        },
        handleScale: {
            mouseWheel: false,
            pinch: false,
            axisPressedMouseMove: {
                time: false,
                price: false,
            },
            axisDoubleClickReset: {
                time: false,
                price: false,
            },
        },
    };
}

function _tvEnsureInteractiveNavigation(entry) {
    if (!entry || !entry.chart || typeof entry.chart.applyOptions !== 'function') return;
    try { entry.chart.applyOptions(_tvInteractiveNavigationOptions()); } catch (e) {}
}

function _tvSetChartInteractionLocked(chartId, locked) {
    if (!chartId) return;
    var entry = window.__PYWRY_TVCHARTS__ && window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.chart || typeof entry.chart.applyOptions !== 'function') return;

    var shouldLock = !!locked;
    if (entry._interactionLocked === shouldLock) return;
    entry._interactionLocked = shouldLock;

    try {
        entry.chart.applyOptions(shouldLock ? _tvLockedNavigationOptions() : _tvInteractiveNavigationOptions());
    } catch (e) {
        try { _tvEnsureInteractiveNavigation(entry); } catch (err) {}
    }

    // Block pointer events on the chart container so internal elements
    // (e.g. the pane separator / plot divider) don't show hover effects.
    if (entry.container) {
        entry.container.style.pointerEvents = shouldLock ? 'none' : '';
    }

    if (shouldLock) {
        // Clear draw hover visuals so no stale hover feedback remains behind the modal.
        if (_drawHoverIdx !== -1 && _drawSelectedChart === chartId) {
            _drawHoverIdx = -1;
            _tvRenderDrawings(chartId);
        }
    }
}

function _tvHideDrawingSettings() {
    _tvHideColorOpacityPopup();
    if (_settingsOverlay && _settingsOverlay.parentNode) {
        _settingsOverlay.parentNode.removeChild(_settingsOverlay);
    }
    if (_settingsOverlayChartId) _tvSetChartInteractionLocked(_settingsOverlayChartId, false);
    _settingsOverlay = null;
    _settingsOverlayChartId = null;
    _tvRefreshLegendVisibility();
}

function _tvHideChartSettings() {
    _tvHideColorOpacityPopup();
    if (_chartSettingsOverlay && _chartSettingsOverlay.parentNode) {
        _chartSettingsOverlay.parentNode.removeChild(_chartSettingsOverlay);
    }
    if (_chartSettingsOverlayChartId) _tvSetChartInteractionLocked(_chartSettingsOverlayChartId, false);
    _chartSettingsOverlay = null;
    _chartSettingsOverlayChartId = null;
    _tvRefreshLegendVisibility();
}

function _tvHideVolumeSettings() {
    _tvHideColorOpacityPopup();
    if (_volumeSettingsOverlay && _volumeSettingsOverlay.parentNode) {
        _volumeSettingsOverlay.parentNode.removeChild(_volumeSettingsOverlay);
    }
    if (_volumeSettingsOverlayChartId) _tvSetChartInteractionLocked(_volumeSettingsOverlayChartId, false);
    _volumeSettingsOverlay = null;
    _volumeSettingsOverlayChartId = null;
    _tvRefreshLegendVisibility();
}

function _tvHideComparePanel() {
    if (_compareOverlay && _compareOverlay.parentNode) {
        _compareOverlay.parentNode.removeChild(_compareOverlay);
    }
    if (_compareOverlayChartId) _tvSetChartInteractionLocked(_compareOverlayChartId, false);
    _compareOverlay = null;
    _compareOverlayChartId = null;
    _tvRefreshLegendVisibility();
}

// ---------------------------------------------------------------------------
// Symbol Search Dialog
// ---------------------------------------------------------------------------
var _symbolSearchOverlay = null;
var _symbolSearchChartId = null;

function _tvHideSymbolSearch() {
    if (_symbolSearchOverlay && _symbolSearchOverlay.parentNode) {
        _symbolSearchOverlay.parentNode.removeChild(_symbolSearchOverlay);
    }
    if (_symbolSearchChartId) _tvSetChartInteractionLocked(_symbolSearchChartId, false);
    _symbolSearchOverlay = null;
    _symbolSearchChartId = null;
    _tvRefreshLegendVisibility();
}

function _tvShowSymbolSearchDialog(chartId) {
    _tvHideSymbolSearch();
    var resolved = _tvResolveChartEntry(chartId);
    if (!resolved || !resolved.entry) return;
    chartId = resolved.chartId;
    var entry = resolved.entry;
    var ds = window.__PYWRY_DRAWINGS__[chartId] || _tvEnsureDrawingLayer(chartId);
    if (!ds) return;

    var overlay = document.createElement('div');
    overlay.className = 'tv-settings-overlay';
    _symbolSearchOverlay = overlay;
    _symbolSearchChartId = chartId;
    _tvSetChartInteractionLocked(chartId, true);
    _tvRefreshLegendVisibility();
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) _tvHideSymbolSearch();
    });
    overlay.addEventListener('mousedown', function(e) { e.stopPropagation(); });
    overlay.addEventListener('wheel', function(e) { e.stopPropagation(); });

    var panel = document.createElement('div');
    panel.className = 'tv-symbol-search-panel';
    overlay.appendChild(panel);

    // Header
    var header = document.createElement('div');
    header.className = 'tv-compare-header';
    var title = document.createElement('h3');
    title.textContent = 'Symbol Search';
    header.appendChild(title);
    var closeBtn = document.createElement('button');
    closeBtn.className = 'tv-settings-close';
    closeBtn.innerHTML = '<svg viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>';
    closeBtn.addEventListener('click', function() { _tvHideSymbolSearch(); });
    header.appendChild(closeBtn);
    panel.appendChild(header);

    // Search row
    var searchRow = document.createElement('div');
    searchRow.className = 'tv-compare-search-row';
    var searchIcon = document.createElement('span');
    searchIcon.className = 'tv-compare-search-icon';
    searchIcon.innerHTML = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="6.5" cy="6.5" r="4"/><line x1="10" y1="10" x2="14" y2="14"/></svg>';
    searchRow.appendChild(searchIcon);
    var searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.className = 'tv-compare-search-input';
    searchInput.placeholder = 'Search symbol...';
    searchInput.autocomplete = 'off';
    searchInput.spellcheck = false;
    searchRow.appendChild(searchInput);
    panel.appendChild(searchRow);

    // Filter row — exchange and type dropdowns from datafeed config
    var filterRow = document.createElement('div');
    filterRow.className = 'tv-symbol-search-filters';

    var exchangeSelect = document.createElement('select');
    exchangeSelect.className = 'tv-symbol-search-filter-select';
    var exchangeDefault = document.createElement('option');
    exchangeDefault.value = '';
    exchangeDefault.textContent = 'All Exchanges';
    exchangeSelect.appendChild(exchangeDefault);

    var typeSelect = document.createElement('select');
    typeSelect.className = 'tv-symbol-search-filter-select';
    var typeDefault = document.createElement('option');
    typeDefault.value = '';
    typeDefault.textContent = 'All Types';
    typeSelect.appendChild(typeDefault);

    // Populate from datafeed config if available
    var cfg = entry._datafeedConfig || {};
    var exchanges = cfg.exchanges || [];
    for (var ei = 0; ei < exchanges.length; ei++) {
        if (!exchanges[ei].value) continue;
        var opt = document.createElement('option');
        opt.value = exchanges[ei].value;
        opt.textContent = exchanges[ei].name || exchanges[ei].value;
        exchangeSelect.appendChild(opt);
    }
    var symTypes = cfg.symbols_types || cfg.symbolsTypes || [];
    for (var ti = 0; ti < symTypes.length; ti++) {
        if (!symTypes[ti].value) continue;
        var topt = document.createElement('option');
        topt.value = symTypes[ti].value;
        topt.textContent = symTypes[ti].name || symTypes[ti].value;
        typeSelect.appendChild(topt);
    }

    filterRow.appendChild(exchangeSelect);
    filterRow.appendChild(typeSelect);
    panel.appendChild(filterRow);

    // Results area
    var searchResults = [];
    var pendingSearchRequestId = null;
    var searchDebounce = null;
    var maxResults = 50;

    var resultsArea = document.createElement('div');
    resultsArea.className = 'tv-symbol-search-results';
    panel.appendChild(resultsArea);

    function normalizeInfo(item) {
        if (!item || typeof item !== 'object') return null;
        var symbol = String(item.symbol || item.ticker || '').trim();
        if (!symbol) return null;
        var ticker = String(item.ticker || '').trim().toUpperCase();
        if (!ticker) {
            ticker = symbol.indexOf(':') >= 0 ? symbol.split(':').pop().trim().toUpperCase() : symbol.toUpperCase();
        }
        return {
            symbol: symbol,
            ticker: ticker,
            displaySymbol: ticker || symbol,
            requestSymbol: ticker || symbol,
            fullName: String(item.fullName || item.full_name || '').trim(),
            description: String(item.description || '').trim(),
            exchange: String(item.exchange || item.listedExchange || item.listed_exchange || '').trim(),
            type: String(item.type || item.symbolType || item.symbol_type || '').trim(),
            currency: String(item.currency || item.currencyCode || item.currency_code || '').trim(),
        };
    }

    function renderResults() {
        resultsArea.innerHTML = '';
        if (!searchResults.length) {
            if (String(searchInput.value || '').trim().length > 0) {
                var empty = document.createElement('div');
                empty.className = 'tv-compare-search-empty';
                empty.textContent = 'No symbols found';
                resultsArea.appendChild(empty);
            }
            return;
        }
        var list = document.createElement('div');
        list.className = 'tv-compare-results-list';
        for (var i = 0; i < searchResults.length; i++) {
            (function(info) {
                var row = document.createElement('div');
                row.className = 'tv-compare-result-row tv-symbol-search-result-row';

                var identity = document.createElement('div');
                identity.className = 'tv-compare-result-identity';

                var badge = document.createElement('div');
                badge.className = 'tv-compare-result-badge';
                badge.textContent = (info.symbol || '?').slice(0, 1);
                identity.appendChild(badge);

                var copy = document.createElement('div');
                copy.className = 'tv-compare-result-copy';

                var top = document.createElement('div');
                top.className = 'tv-compare-result-top';

                var symbolEl = document.createElement('span');
                symbolEl.className = 'tv-compare-result-symbol';
                symbolEl.textContent = info.displaySymbol || info.symbol;
                top.appendChild(symbolEl);

                // Right-side meta: exchange · type
                var parts = [];
                if (info.exchange) parts.push(info.exchange);
                if (info.type) parts.push(info.type);
                if (parts.length) {
                    var meta = document.createElement('span');
                    meta.className = 'tv-compare-result-meta';
                    meta.textContent = parts.join(' \u00b7 ');
                    top.appendChild(meta);
                }

                copy.appendChild(top);

                // Subtitle: actual security name
                var nameText = info.fullName || info.description;
                if (nameText) {
                    var sub = document.createElement('div');
                    sub.className = 'tv-compare-result-sub';
                    sub.textContent = nameText;
                    copy.appendChild(sub);
                }

                identity.appendChild(copy);
                row.appendChild(identity);

                row.addEventListener('click', function() {
                    selectSymbol(info);
                });

                list.appendChild(row);
            })(searchResults[i]);
        }
        resultsArea.appendChild(list);
    }

    function requestSearch(query) {
        query = String(query || '').trim();
        var normalized = query.toUpperCase();
        if (normalized.indexOf(':') >= 0) {
            normalized = normalized.split(':').pop().trim();
        }
        searchResults = [];
        renderResults();
        if (!normalized || normalized.length < 1) return;

        var exch = exchangeSelect.value || '';
        var stype = typeSelect.value || '';

        pendingSearchRequestId = _tvRequestDatafeedSearch(chartId, normalized, maxResults, function(resp) {
            if (!resp || resp.requestId !== pendingSearchRequestId) return;
            pendingSearchRequestId = null;
            if (resp.error) {
                searchResults = [];
                renderResults();
                return;
            }
            var items = Array.isArray(resp.items) ? resp.items : [];
            var parsed = [];
            for (var idx = 0; idx < items.length; idx++) {
                var n = normalizeInfo(items[idx]);
                if (n) parsed.push(n);
            }
            searchResults = parsed;
            renderResults();
        }, exch, stype);
    }

    function selectSymbol(info) {
        var symbol = info.requestSymbol || info.ticker || info.symbol;
        if (!symbol || !window.pywry) return;

        // Resolve full symbol info, then emit data-request to change main series
        _tvRequestDatafeedResolve(chartId, symbol, function(resp) {
            var symbolInfo = null;
            if (resp && resp.symbolInfo) {
                symbolInfo = _tvNormalizeSymbolInfoFull(resp.symbolInfo);
            }

            // -- Update ALL metadata for the new symbol --

            // Payload title + series descriptor (for chart recreate on interval change)
            if (entry.payload) {
                entry.payload.title = symbol.toUpperCase();
                if (entry.payload.series && Array.isArray(entry.payload.series) && entry.payload.series[0]) {
                    entry.payload.series[0].symbol = symbol.toUpperCase();
                }
            }

            // Resolved symbol info — used by Security Info modal, legend, etc.
            if (symbolInfo) {
                entry._mainSymbolInfo = symbolInfo;
                if (!entry._resolvedSymbolInfo) entry._resolvedSymbolInfo = {};
                entry._resolvedSymbolInfo.main = symbolInfo;
            }

            // Reset first-data-request flag for main series so full history is fetched
            if (entry._dataRequestSeen) {
                entry._dataRequestSeen.main = false;
            }

            // Update exchange clock to new timezone
            if (symbolInfo && symbolInfo.timezone) {
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

            // Update chart time axis localization for new timezone
            if (symbolInfo && symbolInfo.timezone && symbolInfo.timezone !== 'Etc/UTC' && entry.chart) {
                try {
                    var tz = symbolInfo.timezone;
                    entry.chart.applyOptions({
                        localization: {
                            timeFormatter: function(ts) {
                                var ms = (typeof ts === 'number' && ts < 1e12) ? ts * 1000 : ts;
                                return new Date(ms).toLocaleString('en-US', {
                                    timeZone: tz,
                                    month: 'short', day: 'numeric',
                                    hour: '2-digit', minute: '2-digit',
                                    hour12: false,
                                });
                            },
                        },
                        timeScale: {
                            tickMarkFormatter: function(time, tickType, locale) {
                                var ms = (typeof time === 'number' && time < 1e12) ? time * 1000 : time;
                                var d = new Date(ms);
                                var opts = { timeZone: tz };
                                if (tickType === 0) { opts.year = 'numeric'; return d.toLocaleString('en-US', opts); }
                                if (tickType === 1) { opts.month = 'short'; return d.toLocaleString('en-US', opts); }
                                if (tickType === 2) { opts.month = 'short'; opts.day = 'numeric'; return d.toLocaleString('en-US', opts); }
                                opts.hour = '2-digit'; opts.minute = '2-digit'; opts.hour12 = false;
                                return d.toLocaleString('en-US', opts);
                            },
                        },
                    });
                } catch (tzErr) {}
            }

            // Unsubscribe old real-time stream, subscribe new
            if (entry._datafeedSubscriptions && entry._datafeedSubscriptions.main && entry.datafeed) {
                var oldGuid = entry._datafeedSubscriptions.main;
                entry.datafeed.unsubscribeBars(oldGuid);
                var activeInterval = _tvCurrentInterval(chartId);
                var newGuid = chartId + '_main_' + activeInterval;
                entry._datafeedSubscriptions.main = newGuid;
                var mainSeries = entry.seriesMap && entry.seriesMap.main;
                entry.datafeed.subscribeBars(symbolInfo || info, activeInterval, function(bar) {
                    var normalized = _tvNormalizeBarsForSeriesType([bar], 'Candlestick');
                    if (normalized.length > 0 && mainSeries) {
                        mainSeries.update(normalized[0]);
                    }
                    if (bar.volume != null && entry.volumeMap && entry.volumeMap.main) {
                        entry.volumeMap.main.update({ time: bar.time, value: bar.volume });
                    }
                }, newGuid, function() {});
            }

            var activeInterval = _tvCurrentInterval(chartId);
            var periodParams = _tvBuildPeriodParams(entry, 'main');
            periodParams.firstDataRequest = true;

            window.pywry.emit('tvchart:data-request', {
                chartId: chartId,
                symbol: symbol.toUpperCase(),
                symbolInfo: symbolInfo || info,
                seriesId: 'main',
                interval: activeInterval,
                resolution: activeInterval,
                periodParams: periodParams,
            });

            // Update the legend's cached base title
            var legendBox = _tvScopedById(chartId, 'tvchart-legend-box');
            if (legendBox) {
                legendBox.dataset.baseTitle = symbol.toUpperCase();
            }
            _tvRefreshLegendTitle(chartId);
            _tvEmitLegendRefresh(chartId);
            _tvRenderHoverLegend(chartId, null);
            _tvHideSymbolSearch();
        });
    }

    // Wire up events
    searchInput.addEventListener('input', function() {
        if (searchDebounce) clearTimeout(searchDebounce);
        searchDebounce = setTimeout(function() {
            requestSearch(searchInput.value);
        }, 180);
    });

    exchangeSelect.addEventListener('change', function() {
        if (String(searchInput.value || '').trim().length > 0) requestSearch(searchInput.value);
    });
    typeSelect.addEventListener('change', function() {
        if (String(searchInput.value || '').trim().length > 0) requestSearch(searchInput.value);
    });

    searchInput.addEventListener('keydown', function(e) {
        e.stopPropagation();
        if (e.key === 'Escape') {
            _tvHideSymbolSearch();
            return;
        }
        if (e.key === 'Enter' && searchResults.length > 0) {
            selectSymbol(searchResults[0]);
        }
    });

    ds.uiLayer.appendChild(overlay);
    searchInput.focus();
}

function _tvHideSeriesSettings() {
    _tvHideColorOpacityPopup();
    if (_seriesSettingsOverlay && _seriesSettingsOverlay.parentNode) {
        _seriesSettingsOverlay.parentNode.removeChild(_seriesSettingsOverlay);
    }
    if (_seriesSettingsOverlayChartId) _tvSetChartInteractionLocked(_seriesSettingsOverlayChartId, false);
    _seriesSettingsOverlay = null;
    _seriesSettingsOverlayChartId = null;
    _seriesSettingsOverlaySeriesId = null;
    _tvRefreshLegendVisibility();
}

function _tvShowSeriesSettings(chartId, seriesId) {
    _tvHideSeriesSettings();
    var resolved = _tvResolveChartEntry(chartId);
    if (!resolved || !resolved.entry) return;
    chartId = resolved.chartId;
    var entry = resolved.entry;
    var seriesApi = entry.seriesMap ? entry.seriesMap[seriesId] : null;
    if (!seriesApi) return;

    var currentType = _tvGuessSeriesType(seriesApi);
    var currentOpts = {};
    try { currentOpts = seriesApi.options() || {}; } catch (e) {}
    var persistedVisibility = (entry._seriesVisibilityIntervals && entry._seriesVisibilityIntervals[seriesId])
        ? entry._seriesVisibilityIntervals[seriesId]
        : null;
    var defaultVisibilityIntervals = {
        seconds: { enabled: true, min: 1, max: 59 },
        minutes: { enabled: true, min: 1, max: 59 },
        hours:   { enabled: true, min: 1, max: 24 },
        days:    { enabled: true, min: 1, max: 366 },
        weeks:   { enabled: true, min: 1, max: 52 },
        months:  { enabled: true, min: 1, max: 12 },
    };
    var persistedStylePrefs = (entry._seriesStylePrefs && entry._seriesStylePrefs[seriesId])
        ? entry._seriesStylePrefs[seriesId]
        : null;
    var initialStyle = (persistedStylePrefs && persistedStylePrefs.style)
        ? persistedStylePrefs.style
        : _ssTypeToStyleName(currentType || 'Line');
    var auxStyle = (entry._seriesStyleAux && entry._seriesStyleAux[seriesId]) ? entry._seriesStyleAux[seriesId] : {};

    var initialState = {
        style: initialStyle,
        priceSource: 'close',
        color: _tvColorToHex(
            currentOpts.color || currentOpts.lineColor || (entry._legendSeriesColors && entry._legendSeriesColors[seriesId]) || '#4c87ff',
            '#4c87ff'
        ),
        lineWidth: _tvClamp(_tvToNumber(currentOpts.lineWidth || currentOpts.width, 2), 1, 4),
        markersVisible: currentOpts.pointMarkersVisible === true,
        areaTopColor: _tvColorToHex(currentOpts.topColor || '#4c87ff', '#4c87ff'),
        areaBottomColor: _tvColorToHex(currentOpts.bottomColor || '#10223f', '#10223f'),
        baselineTopLineColor: _tvColorToHex(currentOpts.topLineColor || '#26a69a', '#26a69a'),
        baselineBottomLineColor: _tvColorToHex(currentOpts.bottomLineColor || '#ef5350', '#ef5350'),
        baselineTopFillColor1: _tvColorToHex(currentOpts.topFillColor1 || '#26a69a', '#26a69a'),
        baselineTopFillColor2: _tvColorToHex(currentOpts.topFillColor2 || '#26a69a', '#26a69a'),
        baselineBottomFillColor1: _tvColorToHex(currentOpts.bottomFillColor1 || '#ef5350', '#ef5350'),
        baselineBottomFillColor2: _tvColorToHex(currentOpts.bottomFillColor2 || '#ef5350', '#ef5350'),
        baselineBaseLevel: _tvToNumber((currentOpts.baseValue && currentOpts.baseValue._level), 50),
        columnsUpColor: _tvColorToHex(currentOpts.upColor || currentOpts.color || '#26a69a', '#26a69a'),
        columnsDownColor: _tvColorToHex(currentOpts.downColor || currentOpts.color || '#ef5350', '#ef5350'),
        barsUpColor: _tvColorToHex(currentOpts.upColor || '#26a69a', '#26a69a'),
        barsDownColor: _tvColorToHex(currentOpts.downColor || '#ef5350', '#ef5350'),
        barsOpenVisible: currentOpts.openVisible !== false,
        priceLineVisible: currentOpts.priceLineVisible !== false,
        overrideMinTick: 'Default',
        visible: currentOpts.visible !== false,
        bodyVisible: true,
        bordersVisible: true,
        wickVisible: true,
        bodyUpColor: _tvColorToHex(currentOpts.upColor || currentOpts.color || '#26a69a', '#26a69a'),
        bodyDownColor: _tvColorToHex(currentOpts.downColor || '#ef5350', '#ef5350'),
        borderUpColor: _tvColorToHex(currentOpts.borderUpColor || currentOpts.upColor || '#26a69a', '#26a69a'),
        borderDownColor: _tvColorToHex(currentOpts.borderDownColor || currentOpts.downColor || '#ef5350', '#ef5350'),
        wickUpColor: _tvColorToHex(currentOpts.wickUpColor || currentOpts.upColor || '#26a69a', '#26a69a'),
        wickDownColor: _tvColorToHex(currentOpts.wickDownColor || currentOpts.downColor || '#ef5350', '#ef5350'),
        hlcHighVisible: auxStyle.highVisible !== false,
        hlcLowVisible: auxStyle.lowVisible !== false,
        hlcCloseVisible: auxStyle.closeVisible !== false,
        hlcHighColor: _tvColorToHex(auxStyle.highColor || _cssVar('--pywry-tvchart-hlcarea-high') || '#089981', '#089981'),
        hlcLowColor: _tvColorToHex(auxStyle.lowColor || _cssVar('--pywry-tvchart-hlcarea-low') || '#f23645', '#f23645'),
        hlcCloseColor: _tvColorToHex(auxStyle.closeColor || (currentOpts.lineColor || currentOpts.color || _cssVar('--pywry-tvchart-hlcarea-close') || '#2962ff'), '#2962ff'),
        hlcFillTopColor: auxStyle.fillTopColor || _cssVar('--pywry-tvchart-hlcarea-fill-up') || 'rgba(8, 153, 129, 0.28)',
        hlcFillBottomColor: auxStyle.fillBottomColor || _cssVar('--pywry-tvchart-hlcarea-fill-down') || 'rgba(242, 54, 69, 0.28)',
        visibilityIntervals: _tvMerge(defaultVisibilityIntervals, persistedVisibility || {}),
    };
    if (persistedStylePrefs) {
        var persistedKeys = Object.keys(initialState);
        for (var pk = 0; pk < persistedKeys.length; pk++) {
            var pkey = persistedKeys[pk];
            if (persistedStylePrefs[pkey] !== undefined) initialState[pkey] = persistedStylePrefs[pkey];
        }
    }
    var draft = _tvMerge({}, initialState);
    var label = _tvLegendSeriesLabel(entry, seriesId);
    var activeTab = 'style';

    var overlay = document.createElement('div');
    overlay.className = 'tv-settings-overlay';
    _seriesSettingsOverlay = overlay;
    _seriesSettingsOverlayChartId = chartId;
    _seriesSettingsOverlaySeriesId = seriesId;
    _tvSetChartInteractionLocked(chartId, true);
    _tvRefreshLegendVisibility();
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) _tvHideSeriesSettings();
    });
    overlay.addEventListener('mousedown', function(e) { e.stopPropagation(); });
    overlay.addEventListener('wheel', function(e) { e.stopPropagation(); });

    var panel = document.createElement('div');
    panel.className = 'tv-settings-panel';
    panel.style.cssText = 'width:620px;max-width:calc(100% - 32px);max-height:72vh;display:flex;flex-direction:column;';
    overlay.appendChild(panel);

    var header = document.createElement('div');
    header.className = 'tv-settings-header';
    header.style.cssText = 'position:relative;flex-direction:column;align-items:stretch;padding-bottom:0;';

    var hdrRow = document.createElement('div');
    hdrRow.style.cssText = 'display:flex;align-items:center;gap:8px;';
    var titleEl = document.createElement('h3');
    titleEl.textContent = label || seriesId;
    hdrRow.appendChild(titleEl);
    var closeBtn = document.createElement('button');
    closeBtn.className = 'tv-settings-close';
    closeBtn.innerHTML = '<svg viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>';
    closeBtn.addEventListener('click', function() { _tvHideSeriesSettings(); });
    hdrRow.appendChild(closeBtn);
    header.appendChild(hdrRow);

    var tabBar = document.createElement('div');
    tabBar.className = 'tv-ind-settings-tabs';
    var styleTab = document.createElement('div');
    styleTab.className = 'tv-ind-settings-tab active';
    styleTab.textContent = 'Style';
    var visTab = document.createElement('div');
    visTab.className = 'tv-ind-settings-tab';
    visTab.textContent = 'Visibility';
    tabBar.appendChild(styleTab);
    tabBar.appendChild(visTab);
    header.appendChild(tabBar);
    panel.appendChild(header);

    var body = document.createElement('div');
    body.className = 'tv-settings-body';
    body.style.cssText = 'flex:1;overflow-y:auto;min-height:80px;';
    panel.appendChild(body);

    function _ssRow(labelText) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        var lbl = document.createElement('label');
        lbl.textContent = labelText;
        row.appendChild(lbl);
        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';
        row.appendChild(ctrl);
        return { row: row, ctrl: ctrl };
    }

    function _ssSelect(opts, value, onChange) {
        var sel = document.createElement('select');
        sel.className = 'ts-select';
        for (var i = 0; i < opts.length; i++) {
            var opt = document.createElement('option');
            opt.value = opts[i].v;
            opt.textContent = opts[i].l;
            if (String(opts[i].v) === String(value)) opt.selected = true;
            sel.appendChild(opt);
        }
        sel.addEventListener('change', function() { onChange(sel.value); });
        return sel;
    }

    function _ssCheckbox(value, onChange) {
        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'ts-checkbox';
        cb.checked = !!value;
        cb.addEventListener('change', function() { onChange(cb.checked); });
        return cb;
    }

    function _ssColorLineControl(value, widthValue, onColor, onWidth) {
        var wrap = document.createElement('div');
        wrap.style.cssText = 'display:flex;align-items:center;gap:8px;';
        var swatch = document.createElement('div');
        swatch.className = 'ts-swatch';
        swatch.dataset.baseColor = _tvColorToHex(value || '#4c87ff', '#4c87ff');
        swatch.dataset.opacity = String(_tvColorOpacityPercent(value, 100));
        swatch.style.background = value;
        swatch.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            _tvShowColorOpacityPopup(
                swatch,
                swatch.dataset.baseColor || value,
                _tvToNumber(swatch.dataset.opacity, 100),
                overlay,
                function(newColor, newOpacity) {
                    swatch.dataset.baseColor = newColor;
                    swatch.dataset.opacity = String(newOpacity);
                    swatch.style.background = _tvColorWithOpacity(newColor, newOpacity, newColor);
                    linePreview.style.background = _tvColorWithOpacity(newColor, newOpacity, newColor);
                    onColor(_tvColorWithOpacity(newColor, newOpacity, newColor));
                }
            );
        });
        var linePreview = document.createElement('div');
        linePreview.style.cssText = 'width:44px;height:2px;background:' + value + ';border-radius:2px;';
        function syncWidth(w) { linePreview.style.height = String(_tvClamp(_tvToNumber(w, 2), 1, 4)) + 'px'; }
        syncWidth(widthValue);
        onWidth(syncWidth);
        wrap.appendChild(swatch);
        wrap.appendChild(linePreview);
        return wrap;
    }

    function _ssDualColorControl(upValue, downValue, onUp, onDown) {
        var wrap = document.createElement('div');
        wrap.style.cssText = 'display:flex;align-items:center;gap:8px;';
        function makeSwatch(initial, onChange) {
            var sw = document.createElement('div');
            sw.className = 'ts-swatch';
            sw.dataset.baseColor = _tvColorToHex(initial || '#4c87ff', '#4c87ff');
            sw.dataset.opacity = String(_tvColorOpacityPercent(initial, 100));
            sw.style.background = initial;
            sw.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                _tvShowColorOpacityPopup(
                    sw,
                    sw.dataset.baseColor || initial,
                    _tvToNumber(sw.dataset.opacity, 100),
                    overlay,
                    function(newColor, newOpacity) {
                        sw.dataset.baseColor = newColor;
                        sw.dataset.opacity = String(newOpacity);
                        sw.style.background = _tvColorWithOpacity(newColor, newOpacity, newColor);
                        onChange(_tvColorWithOpacity(newColor, newOpacity, newColor));
                    }
                );
            });
            wrap.appendChild(sw);
        }
        makeSwatch(upValue, onUp);
        makeSwatch(downValue, onDown);
        return wrap;
    }

    function _ssColorControl(value, onColor) {
        var wrap = document.createElement('div');
        wrap.style.cssText = 'display:flex;align-items:center;gap:8px;';
        var swatch = document.createElement('div');
        swatch.className = 'ts-swatch';
        swatch.dataset.baseColor = _tvColorToHex(value || '#4c87ff', '#4c87ff');
        swatch.dataset.opacity = String(_tvColorOpacityPercent(value, 100));
        swatch.style.background = value;
        swatch.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            _tvShowColorOpacityPopup(
                swatch,
                swatch.dataset.baseColor || value,
                _tvToNumber(swatch.dataset.opacity, 100),
                overlay,
                function(newColor, newOpacity) {
                    swatch.dataset.baseColor = newColor;
                    swatch.dataset.opacity = String(newOpacity);
                    swatch.style.background = _tvColorWithOpacity(newColor, newOpacity, newColor);
                    onColor(_tvColorWithOpacity(newColor, newOpacity, newColor));
                }
            );
        });
        wrap.appendChild(swatch);
        return wrap;
    }

    function _ssIsCandleStyle(styleName) {
        var s = String(styleName || '');
        return s === 'Candles' || s === 'Hollow candles';
    }

    function _ssIsHlcAreaStyle(styleName) {
        return String(styleName || '') === 'HLC area';
    }

    function _ssIsLineLikeStyle(styleName) {
        var s = String(styleName || '');
        return s === 'Line' || s === 'Line with markers' || s === 'Step line';
    }

    function _ssPriceFormatFromTick(value) {
        var v = String(value || 'Default');
        if (v === 'Default') return null;
        if (v === 'Integer') {
            return { type: 'price', precision: 0, minMove: 1 };
        }
        var decMatch = v.match(/^(\d+)\s+decimals?$/i);
        if (decMatch) {
            var precision = _tvClamp(parseInt(decMatch[1], 10) || 0, 0, 15);
            return { type: 'price', precision: precision, minMove: Math.pow(10, -precision) };
        }
        if (v.indexOf('1/') === 0) {
            var denom = parseInt(v.slice(2), 10);
            if (isFinite(denom) && denom > 0) {
                var minMove = 1 / denom;
                var text = String(minMove);
                var precisionFromText = (text.indexOf('.') >= 0) ? (text.split('.')[1] || '').length : 0;
                var precision = _tvClamp(precisionFromText, 1, 8);
                return { type: 'price', precision: precision, minMove: minMove };
            }
        }
        return null;
    }

    function _ssTypeToStyleName(lwcType) {
        var t = String(lwcType || 'Line');
        if (t === 'Candlestick') return 'Candles';
        if (t === 'Bar') return 'Bars';
        if (t === 'Histogram') return 'Columns';
        return t; // Line, Area, Baseline map 1:1
    }

    function _ssStyleConfig(styleName) {
        var s = String(styleName || 'Line');
        if (s === 'Bars') return { seriesType: 'Bar', source: 'close', optionPatch: {} };
        if (s === 'Candles') return { seriesType: 'Candlestick', source: 'close', optionPatch: {} };
        if (s === 'Hollow candles') {
            return {
                seriesType: 'Candlestick',
                source: 'close',
                optionPatch: {
                    upColor: 'rgba(0, 0, 0, 0)',
                },
            };
        }
        if (s === 'Columns') return { seriesType: 'Histogram', source: 'close', optionPatch: {} };
        if (s === 'Line') return { seriesType: 'Line', source: 'close', optionPatch: {} };
        if (s === 'Line with markers') {
            return {
                seriesType: 'Line',
                source: 'close',
                optionPatch: {
                    pointMarkersVisible: true,
                },
            };
        }
        if (s === 'Step line') {
            return {
                seriesType: 'Line',
                source: 'close',
                optionPatch: {
                    lineType: 1,
                },
            };
        }
        if (s === 'Area') return { seriesType: 'Area', source: 'close', optionPatch: {} };
        if (s === 'HLC area') return { seriesType: 'Area', source: 'close', optionPatch: {}, composite: 'hlcArea' };
        if (s === 'Baseline') return { seriesType: 'Baseline', source: 'close', optionPatch: {} };
        if (s === 'HLC bars') return { seriesType: 'Bar', source: 'hlc3', optionPatch: {} };
        if (s === 'High-low') return { seriesType: 'Bar', source: 'close', optionPatch: {} };
        return { seriesType: 'Line', source: 'close', optionPatch: {} };
    }

    function _ssToNumber(v, fallback) {
        var n = Number(v);
        return isFinite(n) ? n : fallback;
    }

    function _ssSourceValue(row, source) {
        var r = row || {};
        var o = _ssToNumber(r.open, _ssToNumber(r.value, null));
        var h = _ssToNumber(r.high, o);
        var l = _ssToNumber(r.low, o);
        var c = _ssToNumber(r.close, _ssToNumber(r.value, o));
        if (source === 'open') return o;
        if (source === 'high') return h;
        if (source === 'low') return l;
        if (source === 'hl2') return (h + l) / 2;
        if (source === 'hlc3') return (h + l + c) / 3;
        if (source === 'ohlc4') return (o + h + l + c) / 4;
        return c;
    }

    function _ssBuildBarsForStyle(rawBars, styleName, seriesType, source) {
        var src = Array.isArray(rawBars) ? rawBars : [];
        if (!src.length) return [];

        var out = [];
        var prevClose = null;
        for (var i = 0; i < src.length; i++) {
            var row = src[i] || {};
            if (row.time == null) continue;

            if (seriesType === 'Line' || seriesType === 'Area' || seriesType === 'Baseline' || seriesType === 'Histogram') {
                out.push({
                    time: row.time,
                    value: _ssSourceValue(row, source),
                });
                continue;
            }

            var base = _ssSourceValue(row, source);
            var open = _ssToNumber(row.open, _ssToNumber(row.value, base));
            var high = _ssToNumber(row.high, Math.max(open, base));
            var low = _ssToNumber(row.low, Math.min(open, base));
            var close = _ssToNumber(row.close, _ssToNumber(row.value, base));

            if (styleName === 'HLC bars') {
                var hlc = _ssSourceValue(row, 'hlc3');
                var o = (prevClose == null) ? hlc : prevClose;
                var c = hlc;
                open = o;
                close = c;
                high = Math.max(o, c);
                low = Math.min(o, c);
                prevClose = c;
            } else if (styleName === 'High-low') {
                var hh = _ssToNumber(row.high, base);
                var ll = _ssToNumber(row.low, base);
                open = ll;
                close = hh;
                high = hh;
                low = ll;
                prevClose = close;
            } else {
                prevClose = close;
            }

            out.push({
                time: row.time,
                open: open,
                high: high,
                low: low,
                close: close,
            });
        }
        return out;
    }

    function _ssLooksLikeOhlcBars(rows) {
        if (!Array.isArray(rows) || !rows.length) return false;
        for (var i = 0; i < rows.length; i++) {
            var r = rows[i] || {};
            if (r.open !== undefined && r.high !== undefined && r.low !== undefined && r.close !== undefined) {
                return true;
            }
        }
        return false;
    }

    function renderBody() {
        body.innerHTML = '';
        if (activeTab === 'style') {
            var styleRow = _ssRow('Style');
            styleRow.ctrl.appendChild(_ssSelect([
                { v: 'Bars', l: 'Bars' },
                { v: 'Candles', l: 'Candles' },
                { v: 'Hollow candles', l: 'Hollow candles' },
                { v: 'Columns', l: 'Columns' },
                { v: 'Line', l: 'Line' },
                { v: 'Line with markers', l: 'Line with markers' },
                { v: 'Step line', l: 'Step line' },
                { v: 'Area', l: 'Area' },
                { v: 'HLC area', l: 'HLC area' },
                { v: 'Baseline', l: 'Baseline' },
                { v: 'HLC bars', l: 'HLC bars' },
                { v: 'High-low', l: 'High-low' },
            ], draft.style, function(v) {
                draft.style = v;
                renderBody();
            }));
            body.appendChild(styleRow.row);

            var selectedStyle = String(draft.style || 'Line');
            if (_ssIsCandleStyle(selectedStyle)) {
                var bodyRow = _ssRow('Body');
                var bodyWrap = document.createElement('div');
                bodyWrap.style.cssText = 'display:flex;align-items:center;gap:10px;';
                bodyWrap.appendChild(_ssCheckbox(draft.bodyVisible !== false, function(v) { draft.bodyVisible = v; }));
                bodyWrap.appendChild(_ssDualColorControl(
                    draft.bodyUpColor,
                    draft.bodyDownColor,
                    function(v) { draft.bodyUpColor = v; },
                    function(v) { draft.bodyDownColor = v; }
                ));
                bodyRow.ctrl.appendChild(bodyWrap);
                body.appendChild(bodyRow.row);

                var borderRow = _ssRow('Borders');
                var borderWrap = document.createElement('div');
                borderWrap.style.cssText = 'display:flex;align-items:center;gap:10px;';
                borderWrap.appendChild(_ssCheckbox(draft.bordersVisible !== false, function(v) { draft.bordersVisible = v; }));
                borderWrap.appendChild(_ssDualColorControl(
                    draft.borderUpColor,
                    draft.borderDownColor,
                    function(v) { draft.borderUpColor = v; },
                    function(v) { draft.borderDownColor = v; }
                ));
                borderRow.ctrl.appendChild(borderWrap);
                body.appendChild(borderRow.row);

                var wickRow = _ssRow('Wick');
                var wickWrap = document.createElement('div');
                wickWrap.style.cssText = 'display:flex;align-items:center;gap:10px;';
                wickWrap.appendChild(_ssCheckbox(draft.wickVisible !== false, function(v) { draft.wickVisible = v; }));
                wickWrap.appendChild(_ssDualColorControl(
                    draft.wickUpColor,
                    draft.wickDownColor,
                    function(v) { draft.wickUpColor = v; },
                    function(v) { draft.wickDownColor = v; }
                ));
                wickRow.ctrl.appendChild(wickWrap);
                body.appendChild(wickRow.row);
            } else if (_ssIsHlcAreaStyle(selectedStyle)) {
                var highRow = _ssRow('High line');
                var highWrap = document.createElement('div');
                highWrap.style.cssText = 'display:flex;align-items:center;gap:10px;';
                highWrap.appendChild(_ssCheckbox(draft.hlcHighVisible !== false, function(v) { draft.hlcHighVisible = v; }));
                highWrap.appendChild(_ssColorLineControl(draft.hlcHighColor, draft.lineWidth, function(v) { draft.hlcHighColor = v; }, function() {}));
                highRow.ctrl.appendChild(highWrap);
                body.appendChild(highRow.row);

                var lowRow = _ssRow('Low line');
                var lowWrap = document.createElement('div');
                lowWrap.style.cssText = 'display:flex;align-items:center;gap:10px;';
                lowWrap.appendChild(_ssCheckbox(draft.hlcLowVisible !== false, function(v) { draft.hlcLowVisible = v; }));
                lowWrap.appendChild(_ssColorLineControl(draft.hlcLowColor, draft.lineWidth, function(v) { draft.hlcLowColor = v; }, function() {}));
                lowRow.ctrl.appendChild(lowWrap);
                body.appendChild(lowRow.row);

                var closeLineRow = _ssRow('Close line');
                closeLineRow.ctrl.appendChild(_ssColorLineControl(draft.hlcCloseColor, draft.lineWidth, function(v) { draft.hlcCloseColor = v; }, function() {}));
                body.appendChild(closeLineRow.row);

                var fillRow = _ssRow('Fill');
                fillRow.ctrl.appendChild(_ssDualColorControl(
                    draft.hlcFillTopColor,
                    draft.hlcFillBottomColor,
                    function(v) { draft.hlcFillTopColor = v; },
                    function(v) { draft.hlcFillBottomColor = v; }
                ));
                body.appendChild(fillRow.row);
            } else if (selectedStyle === 'Area') {
                var areaSourceRow = _ssRow('Price source');
                areaSourceRow.ctrl.appendChild(_ssSelect([
                    { v: 'open', l: 'Open' },
                    { v: 'high', l: 'High' },
                    { v: 'low', l: 'Low' },
                    { v: 'close', l: 'Close' },
                    { v: 'hl2', l: '(H + L)/2' },
                    { v: 'hlc3', l: '(H + L + C)/3' },
                    { v: 'ohlc4', l: '(O + H + L + C)/4' },
                ], draft.priceSource, function(v) { draft.priceSource = v; }));
                body.appendChild(areaSourceRow.row);

                var areaLineRow = _ssRow('Line');
                var areaWidthSync = function() {};
                areaLineRow.ctrl.appendChild(_ssColorLineControl(
                    draft.color,
                    draft.lineWidth,
                    function(v) { draft.color = v; },
                    function(sync) { areaWidthSync = sync; }
                ));
                body.appendChild(areaLineRow.row);

                var areaWidthRow = _ssRow('Line width');
                areaWidthRow.ctrl.appendChild(_ssSelect([
                    { v: 1, l: '1px' },
                    { v: 2, l: '2px' },
                    { v: 3, l: '3px' },
                    { v: 4, l: '4px' },
                ], draft.lineWidth, function(v) {
                    draft.lineWidth = _tvClamp(_tvToNumber(v, 2), 1, 4);
                    areaWidthSync(draft.lineWidth);
                }));
                body.appendChild(areaWidthRow.row);

                var areaFillRow = _ssRow('Fill');
                areaFillRow.ctrl.appendChild(_ssDualColorControl(
                    draft.areaTopColor,
                    draft.areaBottomColor,
                    function(v) { draft.areaTopColor = v; },
                    function(v) { draft.areaBottomColor = v; }
                ));
                body.appendChild(areaFillRow.row);
            } else if (selectedStyle === 'Baseline') {
                var baseSourceRow = _ssRow('Price source');
                baseSourceRow.ctrl.appendChild(_ssSelect([
                    { v: 'open', l: 'Open' },
                    { v: 'high', l: 'High' },
                    { v: 'low', l: 'Low' },
                    { v: 'close', l: 'Close' },
                    { v: 'hl2', l: '(H + L)/2' },
                    { v: 'hlc3', l: '(H + L + C)/3' },
                    { v: 'ohlc4', l: '(O + H + L + C)/4' },
                ], draft.priceSource, function(v) { draft.priceSource = v; }));
                body.appendChild(baseSourceRow.row);

                var topLineRow = _ssRow('Top line');
                topLineRow.ctrl.appendChild(_ssColorControl(draft.baselineTopLineColor, function(v) { draft.baselineTopLineColor = v; }));
                body.appendChild(topLineRow.row);

                var bottomLineRow = _ssRow('Bottom line');
                bottomLineRow.ctrl.appendChild(_ssColorControl(draft.baselineBottomLineColor, function(v) { draft.baselineBottomLineColor = v; }));
                body.appendChild(bottomLineRow.row);

                var topFillRow = _ssRow('Top fill');
                topFillRow.ctrl.appendChild(_ssDualColorControl(
                    draft.baselineTopFillColor1,
                    draft.baselineTopFillColor2,
                    function(v) { draft.baselineTopFillColor1 = v; },
                    function(v) { draft.baselineTopFillColor2 = v; }
                ));
                body.appendChild(topFillRow.row);

                var bottomFillRow = _ssRow('Bottom fill');
                bottomFillRow.ctrl.appendChild(_ssDualColorControl(
                    draft.baselineBottomFillColor1,
                    draft.baselineBottomFillColor2,
                    function(v) { draft.baselineBottomFillColor1 = v; },
                    function(v) { draft.baselineBottomFillColor2 = v; }
                ));
                body.appendChild(bottomFillRow.row);

                var baseValueRow = _ssRow('Base level');
                var baseLevelWrap = document.createElement('span');
                baseLevelWrap.style.display = 'inline-flex';
                baseLevelWrap.style.alignItems = 'center';
                baseLevelWrap.style.gap = '4px';
                var baseValueInput = document.createElement('input');
                baseValueInput.type = 'number';
                baseValueInput.className = 'ts-input';
                baseValueInput.style.width = '80px';
                baseValueInput.min = '0';
                baseValueInput.max = '100';
                baseValueInput.value = String(_tvToNumber(draft.baselineBaseLevel, 50));
                baseValueInput.addEventListener('input', function() {
                    draft.baselineBaseLevel = _tvClamp(_tvToNumber(baseValueInput.value, 50), 0, 100);
                });
                var pctLabel = document.createElement('span');
                pctLabel.textContent = '%';
                pctLabel.style.opacity = '0.6';
                baseLevelWrap.appendChild(baseValueInput);
                baseLevelWrap.appendChild(pctLabel);
                baseValueRow.ctrl.appendChild(baseLevelWrap);
                body.appendChild(baseValueRow.row);
            } else if (selectedStyle === 'Columns') {
                var columnsSourceRow = _ssRow('Price source');
                columnsSourceRow.ctrl.appendChild(_ssSelect([
                    { v: 'open', l: 'Open' },
                    { v: 'high', l: 'High' },
                    { v: 'low', l: 'Low' },
                    { v: 'close', l: 'Close' },
                    { v: 'hl2', l: '(H + L)/2' },
                    { v: 'hlc3', l: '(H + L + C)/3' },
                    { v: 'ohlc4', l: '(O + H + L + C)/4' },
                ], draft.priceSource, function(v) { draft.priceSource = v; }));
                body.appendChild(columnsSourceRow.row);

                var columnsColorRow = _ssRow('Columns');
                columnsColorRow.ctrl.appendChild(_ssDualColorControl(
                    draft.columnsUpColor,
                    draft.columnsDownColor,
                    function(v) { draft.columnsUpColor = v; },
                    function(v) { draft.columnsDownColor = v; }
                ));
                body.appendChild(columnsColorRow.row);
            } else if (selectedStyle === 'Bars' || selectedStyle === 'HLC bars' || selectedStyle === 'High-low') {
                if (selectedStyle === 'Bars') {
                    var barsSourceRow = _ssRow('Price source');
                    barsSourceRow.ctrl.appendChild(_ssSelect([
                        { v: 'open', l: 'Open' },
                        { v: 'high', l: 'High' },
                        { v: 'low', l: 'Low' },
                        { v: 'close', l: 'Close' },
                        { v: 'hl2', l: '(H + L)/2' },
                        { v: 'hlc3', l: '(H + L + C)/3' },
                        { v: 'ohlc4', l: '(O + H + L + C)/4' },
                    ], draft.priceSource, function(v) { draft.priceSource = v; }));
                    body.appendChild(barsSourceRow.row);
                }

                var barsColorRow = _ssRow('Up/Down colors');
                barsColorRow.ctrl.appendChild(_ssDualColorControl(
                    draft.barsUpColor,
                    draft.barsDownColor,
                    function(v) { draft.barsUpColor = v; },
                    function(v) { draft.barsDownColor = v; }
                ));
                body.appendChild(barsColorRow.row);

                var openTickRow = _ssRow('Open tick');
                openTickRow.ctrl.appendChild(_ssCheckbox(draft.barsOpenVisible !== false, function(v) { draft.barsOpenVisible = v; }));
                body.appendChild(openTickRow.row);
            } else {
                var sourceRow = _ssRow('Price source');
                sourceRow.ctrl.appendChild(_ssSelect([
                    { v: 'open', l: 'Open' },
                    { v: 'high', l: 'High' },
                    { v: 'low', l: 'Low' },
                    { v: 'close', l: 'Close' },
                    { v: 'hl2', l: '(H + L)/2' },
                    { v: 'hlc3', l: '(H + L + C)/3' },
                    { v: 'ohlc4', l: '(O + H + L + C)/4' },
                ], draft.priceSource, function(v) { draft.priceSource = v; }));
                body.appendChild(sourceRow.row);

                var lineRow = _ssRow('Line');
                var widthSync = function() {};
                var lineCtrl = _ssColorLineControl(draft.color, draft.lineWidth, function(v) { draft.color = v; }, function(sync) { widthSync = sync; });
                lineRow.ctrl.appendChild(lineCtrl);
                body.appendChild(lineRow.row);

                var widthRow = _ssRow('Line width');
                widthRow.ctrl.appendChild(_ssSelect([
                    { v: 1, l: '1px' },
                    { v: 2, l: '2px' },
                    { v: 3, l: '3px' },
                    { v: 4, l: '4px' },
                ], draft.lineWidth, function(v) {
                    draft.lineWidth = _tvClamp(_tvToNumber(v, 2), 1, 4);
                    widthSync(draft.lineWidth);
                }));
                body.appendChild(widthRow.row);

                if (selectedStyle === 'Line with markers') {
                    var markersRow = _ssRow('Markers');
                    markersRow.ctrl.appendChild(_ssCheckbox(draft.markersVisible !== false, function(v) {
                        draft.markersVisible = v;
                    }));
                    body.appendChild(markersRow.row);
                }
            }

            var priceLineRow = _ssRow('Price line');
            priceLineRow.ctrl.appendChild(_ssCheckbox(draft.priceLineVisible, function(v) { draft.priceLineVisible = v; }));
            body.appendChild(priceLineRow.row);

            var tickRow = _ssRow('Override min tick');
            tickRow.ctrl.appendChild(_ssSelect([
                { v: 'Default', l: 'Default' },
                { v: 'Integer', l: 'Integer' },
                { v: '1 decimals', l: '1 decimal' },
                { v: '2 decimals', l: '2 decimals' },
                { v: '3 decimals', l: '3 decimals' },
                { v: '4 decimals', l: '4 decimals' },
                { v: '5 decimals', l: '5 decimals' },
                { v: '6 decimals', l: '6 decimals' },
                { v: '7 decimals', l: '7 decimals' },
                { v: '8 decimals', l: '8 decimals' },
                { v: '9 decimals', l: '9 decimals' },
                { v: '10 decimals', l: '10 decimals' },
                { v: '11 decimals', l: '11 decimals' },
                { v: '12 decimals', l: '12 decimals' },
                { v: '13 decimals', l: '13 decimals' },
                { v: '14 decimals', l: '14 decimals' },
                { v: '15 decimals', l: '15 decimals' },
                { v: '1/2', l: '1/2' },
                { v: '1/4', l: '1/4' },
                { v: '1/8', l: '1/8' },
                { v: '1/16', l: '1/16' },
                { v: '1/32', l: '1/32' },
                { v: '1/64', l: '1/64' },
                { v: '1/128', l: '1/128' },
                { v: '1/320', l: '1/320' },
            ], draft.overrideMinTick, function(v) { draft.overrideMinTick = v; }));
            body.appendChild(tickRow.row);
        } else {
            var visibilityDefs = [
                { key: 'seconds', label: 'Seconds', max: 59 },
                { key: 'minutes', label: 'Minutes', max: 59 },
                { key: 'hours', label: 'Hours', max: 24 },
                { key: 'days', label: 'Days', max: 366 },
                { key: 'weeks', label: 'Weeks', max: 52 },
                { key: 'months', label: 'Months', max: 12 },
            ];
            for (var vi = 0; vi < visibilityDefs.length; vi++) {
                (function(def) {
                    var cfg = draft.visibilityIntervals[def.key] || { enabled: true, min: 1, max: def.max };
                    var row = document.createElement('div');
                    row.className = 'tv-settings-row tv-settings-row-spaced';
                    row.style.alignItems = 'center';

                    var lhs = document.createElement('div');
                    lhs.style.cssText = 'display:flex;align-items:center;gap:10px;min-width:120px;';
                    var cb = _ssCheckbox(cfg.enabled !== false, function(v) {
                        cfg.enabled = !!v;
                        draft.visibilityIntervals[def.key] = cfg;
                    });
                    lhs.appendChild(cb);
                    var lbl = document.createElement('span');
                    lbl.textContent = def.label;
                    lbl.style.color = 'var(--pywry-tvchart-text)';
                    lhs.appendChild(lbl);
                    row.appendChild(lhs);

                    var minInput = document.createElement('input');
                    minInput.type = 'number';
                    minInput.className = 'ts-input';
                    minInput.style.width = '74px';
                    minInput.min = '1';
                    minInput.max = String(def.max);
                    minInput.value = String(_tvClamp(_tvToNumber(cfg.min, 1), 1, def.max));
                    row.appendChild(minInput);

                    var track = document.createElement('div');
                    track.style.cssText = 'position:relative;flex:1;min-width:130px;max-width:190px;height:14px;';
                    var rail = document.createElement('div');
                    rail.style.cssText = 'position:absolute;left:0;right:0;top:6px;height:3px;border-radius:3px;background:var(--pywry-tvchart-border-strong);';
                    var leftKnob = document.createElement('span');
                    var rightKnob = document.createElement('span');
                    leftKnob.style.cssText = 'position:absolute;top:1px;width:12px;height:12px;border-radius:50%;background:var(--pywry-tvchart-panel-bg);border:2px solid #fff;box-sizing:border-box;';
                    rightKnob.style.cssText = 'position:absolute;top:1px;width:12px;height:12px;border-radius:50%;background:var(--pywry-tvchart-panel-bg);border:2px solid #fff;box-sizing:border-box;';
                    track.appendChild(rail);
                    track.appendChild(leftKnob);
                    track.appendChild(rightKnob);
                    row.appendChild(track);

                    var maxInput = document.createElement('input');
                    maxInput.type = 'number';
                    maxInput.className = 'ts-input';
                    maxInput.style.width = '74px';
                    maxInput.min = '1';
                    maxInput.max = String(def.max);
                    maxInput.value = String(_tvClamp(_tvToNumber(cfg.max, def.max), 1, def.max));
                    row.appendChild(maxInput);

                    function syncKnobs() {
                        var minVal = _tvClamp(_tvToNumber(minInput.value, 1), 1, def.max);
                        var maxVal = _tvClamp(_tvToNumber(maxInput.value, def.max), 1, def.max);
                        if (minVal > maxVal) {
                            if (document.activeElement === minInput) maxVal = minVal;
                            else minVal = maxVal;
                        }
                        minInput.value = String(minVal);
                        maxInput.value = String(maxVal);
                        cfg.min = minVal;
                        cfg.max = maxVal;
                        draft.visibilityIntervals[def.key] = cfg;
                        var lp = ((minVal - 1) / Math.max(def.max - 1, 1)) * 100;
                        var rp = ((maxVal - 1) / Math.max(def.max - 1, 1)) * 100;
                        leftKnob.style.left = 'calc(' + lp + '% - 6px)';
                        rightKnob.style.left = 'calc(' + rp + '% - 6px)';
                    }

                    minInput.addEventListener('input', syncKnobs);
                    maxInput.addEventListener('input', syncKnobs);
                    syncKnobs();
                    body.appendChild(row);
                })(visibilityDefs[vi]);
            }
        }
    }

    styleTab.addEventListener('click', function() {
        activeTab = 'style';
        styleTab.classList.add('active');
        visTab.classList.remove('active');
        renderBody();
    });
    visTab.addEventListener('click', function() {
        activeTab = 'visibility';
        visTab.classList.add('active');
        styleTab.classList.remove('active');
        renderBody();
    });

    var footer = document.createElement('div');
    footer.className = 'tv-settings-footer';
    footer.style.position = 'relative';

    var defaultsWrap = document.createElement('div');
    defaultsWrap.className = 'tv-settings-template-wrap';
    var defaultsBtn = document.createElement('button');
    defaultsBtn.className = 'ts-btn-template';
    defaultsBtn.textContent = 'Defaults';
    defaultsWrap.appendChild(defaultsBtn);
    var defaultsMenu = null;
    function closeDefaultsMenu() {
        if (defaultsMenu && defaultsMenu.parentNode) defaultsMenu.parentNode.removeChild(defaultsMenu);
        defaultsMenu = null;
        defaultsBtn.classList.remove('open');
    }
    defaultsBtn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        if (defaultsMenu) {
            closeDefaultsMenu();
            return;
        }
        defaultsMenu = document.createElement('div');
        defaultsMenu.className = 'tv-settings-template-menu';
        var resetBtn = document.createElement('button');
        resetBtn.className = 'tv-settings-template-item';
        resetBtn.textContent = 'Reset settings';
        resetBtn.addEventListener('click', function() {
            draft = _tvMerge({}, initialState);
            renderBody();
            closeDefaultsMenu();
        });
        defaultsMenu.appendChild(resetBtn);
        var saveBtn = document.createElement('button');
        saveBtn.className = 'tv-settings-template-item';
        saveBtn.textContent = 'Save as default';
        saveBtn.addEventListener('click', function() { closeDefaultsMenu(); });
        defaultsMenu.appendChild(saveBtn);
        defaultsWrap.appendChild(defaultsMenu);
        defaultsBtn.classList.add('open');
    });
    overlay.addEventListener('mousedown', function(e) {
        if (defaultsMenu && defaultsWrap && !defaultsWrap.contains(e.target)) closeDefaultsMenu();
    });
    footer.appendChild(defaultsWrap);

    var cancelBtn = document.createElement('button');
    cancelBtn.className = 'ts-btn-cancel';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.addEventListener('click', function() { _tvHideSeriesSettings(); });
    footer.appendChild(cancelBtn);

    var okBtn = document.createElement('button');
    okBtn.className = 'ts-btn-ok';
    okBtn.textContent = 'Ok';
    okBtn.addEventListener('click', function() {
        var selectedStyle = String(draft.style || 'Line');
        var cfg = _ssStyleConfig(selectedStyle);
        var targetType = cfg.seriesType;

        // Fast path: series type unchanged — just applyOptions, never recreate.
        var oldSeries = entry.seriesMap ? entry.seriesMap[seriesId] : null;
        var oldType = oldSeries ? _tvGuessSeriesType(oldSeries) : null;
        if (oldSeries && oldType === targetType
            && selectedStyle !== 'Columns' && !_ssIsHlcAreaStyle(selectedStyle)) {
            var patchOpts = {};

            if (_ssIsCandleStyle(selectedStyle)) {
                var hidden = 'rgba(0, 0, 0, 0)';
                patchOpts.upColor = (draft.bodyVisible !== false) ? draft.bodyUpColor : hidden;
                patchOpts.downColor = (draft.bodyVisible !== false) ? draft.bodyDownColor : hidden;
                patchOpts.borderUpColor = (draft.bordersVisible !== false) ? draft.borderUpColor : hidden;
                patchOpts.borderDownColor = (draft.bordersVisible !== false) ? draft.borderDownColor : hidden;
                patchOpts.wickUpColor = (draft.wickVisible !== false) ? draft.wickUpColor : hidden;
                patchOpts.wickDownColor = (draft.wickVisible !== false) ? draft.wickDownColor : hidden;
                if (selectedStyle === 'Hollow candles') patchOpts.upColor = hidden;
            } else if (_ssIsLineLikeStyle(selectedStyle)) {
                patchOpts.color = draft.color;
                patchOpts.lineColor = draft.color;
                patchOpts.lineWidth = _tvClamp(_tvToNumber(draft.lineWidth, 2), 1, 4);
                patchOpts.pointMarkersVisible = selectedStyle === 'Line with markers' ? (draft.markersVisible !== false) : false;
                patchOpts.lineType = selectedStyle === 'Step line' ? 1 : 0;
            } else if (selectedStyle === 'Area') {
                patchOpts.lineColor = draft.color;
                patchOpts.topColor = draft.areaTopColor;
                patchOpts.bottomColor = draft.areaBottomColor;
                patchOpts.lineWidth = _tvClamp(_tvToNumber(draft.lineWidth, 2), 1, 4);
            } else if (selectedStyle === 'Baseline') {
                patchOpts.topLineColor = draft.baselineTopLineColor;
                patchOpts.bottomLineColor = draft.baselineBottomLineColor;
                patchOpts.topFillColor1 = draft.baselineTopFillColor1;
                patchOpts.topFillColor2 = draft.baselineTopFillColor2;
                patchOpts.bottomFillColor1 = draft.baselineBottomFillColor1;
                patchOpts.bottomFillColor2 = draft.baselineBottomFillColor2;
                patchOpts.lineWidth = _tvClamp(_tvToNumber(draft.lineWidth, 2), 1, 4);
            } else if (selectedStyle === 'Bars' || selectedStyle === 'HLC bars' || selectedStyle === 'High-low') {
                patchOpts.upColor = draft.barsUpColor;
                patchOpts.downColor = draft.barsDownColor;
                patchOpts.openVisible = draft.barsOpenVisible !== false;
            }

            var tickPriceFormat = _ssPriceFormatFromTick(draft.overrideMinTick);
            if (tickPriceFormat) patchOpts.priceFormat = tickPriceFormat;

            try { oldSeries.applyOptions(patchOpts); } catch (e) {}

            // Persist preferences
            if (!entry._seriesStylePrefs) entry._seriesStylePrefs = {};
            entry._seriesStylePrefs[seriesId] = {
                style: draft.style,
                priceSource: draft.priceSource,
                color: draft.color,
                lineWidth: draft.lineWidth,
                markersVisible: draft.markersVisible,
                areaTopColor: draft.areaTopColor,
                areaBottomColor: draft.areaBottomColor,
                baselineTopLineColor: draft.baselineTopLineColor,
                baselineBottomLineColor: draft.baselineBottomLineColor,
                baselineTopFillColor1: draft.baselineTopFillColor1,
                baselineTopFillColor2: draft.baselineTopFillColor2,
                baselineBottomFillColor1: draft.baselineBottomFillColor1,
                baselineBottomFillColor2: draft.baselineBottomFillColor2,
                baselineBaseLevel: draft.baselineBaseLevel,
                columnsUpColor: draft.columnsUpColor,
                columnsDownColor: draft.columnsDownColor,
                barsUpColor: draft.barsUpColor,
                barsDownColor: draft.barsDownColor,
                barsOpenVisible: draft.barsOpenVisible,
                bodyVisible: draft.bodyVisible,
                bordersVisible: draft.bordersVisible,
                wickVisible: draft.wickVisible,
                bodyUpColor: draft.bodyUpColor,
                bodyDownColor: draft.bodyDownColor,
                borderUpColor: draft.borderUpColor,
                borderDownColor: draft.borderDownColor,
                wickUpColor: draft.wickUpColor,
                wickDownColor: draft.wickDownColor,
                priceLineVisible: draft.priceLineVisible,
                overrideMinTick: draft.overrideMinTick,
                hlcHighVisible: draft.hlcHighVisible,
                hlcLowVisible: draft.hlcLowVisible,
                hlcCloseVisible: draft.hlcCloseVisible,
                hlcHighColor: draft.hlcHighColor,
                hlcLowColor: draft.hlcLowColor,
                hlcCloseColor: draft.hlcCloseColor,
                hlcFillTopColor: draft.hlcFillTopColor,
                hlcFillBottomColor: draft.hlcFillBottomColor,
            };
            if (!entry._seriesVisibilityIntervals) entry._seriesVisibilityIntervals = {};
            entry._seriesVisibilityIntervals[seriesId] = _tvMerge({}, draft.visibilityIntervals || {});

            // Update legend color
            var legendColor = draft.color;
            if (_ssIsCandleStyle(selectedStyle)) legendColor = draft.bodyUpColor;
            if (selectedStyle === 'Columns') legendColor = draft.columnsUpColor;
            if (selectedStyle === 'Bars' || selectedStyle === 'HLC bars' || selectedStyle === 'High-low') legendColor = draft.barsUpColor;
            if (selectedStyle === 'Area') legendColor = draft.color;
            if (selectedStyle === 'Baseline') legendColor = draft.baselineTopLineColor;
            if (!entry._legendSeriesColors) entry._legendSeriesColors = {};
            entry._legendSeriesColors[seriesId] = legendColor;

            _tvHideSeriesSettings();
            _tvRenderHoverLegend(chartId, null);
            return;
        }

        // Full rebuild path — style changed, need to destroy and recreate series
        var sourceForStyle = cfg.source || draft.priceSource || 'close';
        var payloadSeries = _tvFindPayloadSeries(entry, seriesId);
        if (!entry._seriesCanonicalRawData) entry._seriesCanonicalRawData = {};
        var canonicalBars = entry._seriesCanonicalRawData[seriesId];
        var payloadBars = (payloadSeries && Array.isArray(payloadSeries.bars)) ? payloadSeries.bars : [];
        var fallbackBars = (entry._seriesRawData && entry._seriesRawData[seriesId]) ? entry._seriesRawData[seriesId] : [];
        if (!Array.isArray(canonicalBars) || !canonicalBars.length) {
            if (_ssLooksLikeOhlcBars(payloadBars)) {
                canonicalBars = payloadBars;
            } else if (_ssLooksLikeOhlcBars(fallbackBars)) {
                canonicalBars = fallbackBars;
            }
            if (Array.isArray(canonicalBars) && canonicalBars.length) {
                entry._seriesCanonicalRawData[seriesId] = canonicalBars;
            }
        }
        var rawBars = (Array.isArray(canonicalBars) && canonicalBars.length)
            ? canonicalBars
            : (payloadBars.length ? payloadBars : fallbackBars);
        var transformedRawBars = _ssBuildBarsForStyle(rawBars, String(draft.style || ''), targetType, sourceForStyle);
        var normalizedBars = _tvNormalizeBarsForSeriesType(transformedRawBars, targetType);

        if (selectedStyle === 'Columns') {
            var histogramBars = [];
            var prevValue = null;
            for (var ci = 0; ci < rawBars.length; ci++) {
                var crow = rawBars[ci] || {};
                if (crow.time == null) continue;
                var cval = _ssSourceValue(crow, sourceForStyle);
                var isUp = (prevValue == null) ? true : (cval >= prevValue);
                histogramBars.push({
                    time: crow.time,
                    value: cval,
                    color: isUp ? draft.columnsUpColor : draft.columnsDownColor,
                });
                prevValue = cval;
            }
            normalizedBars = histogramBars;
            transformedRawBars = histogramBars;
        }

        var oldSeries = entry.seriesMap ? entry.seriesMap[seriesId] : null;
        var paneIndex = 0;
        if (!_tvIsMainSeriesId(seriesId) && entry._comparePaneBySeries && entry._comparePaneBySeries[seriesId] !== undefined) {
            paneIndex = entry._comparePaneBySeries[seriesId];
        }

        var baseSeriesOptions = _tvBuildSeriesOptions(
            (payloadSeries && payloadSeries.seriesOptions) ? payloadSeries.seriesOptions : {},
            targetType,
            entry.theme
        );

        var rebuiltOptions = _tvMerge(baseSeriesOptions, {
            priceLineVisible: !!draft.priceLineVisible,
            lastValueVisible: !!draft.priceLineVisible,
            visible: draft.visible !== false,
        });

        if (_tvIsMainSeriesId(seriesId)) {
            rebuiltOptions.priceScaleId = _tvResolveScalePlacement(entry);
            if (entry._comparePaneBySeries && entry._comparePaneBySeries.main !== undefined) {
                delete entry._comparePaneBySeries.main;
            }
        }

        if (_ssIsLineLikeStyle(selectedStyle)) {
            rebuiltOptions.color = draft.color;
            rebuiltOptions.lineColor = draft.color;
            rebuiltOptions.lineWidth = _tvClamp(_tvToNumber(draft.lineWidth, 2), 1, 4);
            rebuiltOptions.pointMarkersVisible = selectedStyle === 'Line with markers' ? (draft.markersVisible !== false) : false;
            rebuiltOptions.lineType = selectedStyle === 'Step line' ? 1 : 0;
        } else if (selectedStyle === 'Area') {
            rebuiltOptions.lineColor = draft.color;
            rebuiltOptions.topColor = draft.areaTopColor;
            rebuiltOptions.bottomColor = draft.areaBottomColor;
            rebuiltOptions.lineWidth = _tvClamp(_tvToNumber(draft.lineWidth, 2), 1, 4);
        } else if (selectedStyle === 'Baseline') {
            rebuiltOptions.topLineColor = draft.baselineTopLineColor;
            rebuiltOptions.bottomLineColor = draft.baselineBottomLineColor;
            rebuiltOptions.topFillColor1 = draft.baselineTopFillColor1;
            rebuiltOptions.topFillColor2 = draft.baselineTopFillColor2;
            rebuiltOptions.bottomFillColor1 = draft.baselineBottomFillColor1;
            rebuiltOptions.bottomFillColor2 = draft.baselineBottomFillColor2;
            rebuiltOptions.lineWidth = _tvClamp(_tvToNumber(draft.lineWidth, 2), 1, 4);
            var baseLevel = _tvClamp(_tvToNumber(draft.baselineBaseLevel, 50), 0, 100);
            var basePrice = _tvComputeBaselineValue(rawBars, baseLevel);
            rebuiltOptions.baseValue = { type: 'price', price: basePrice, _level: baseLevel };
        } else if (selectedStyle === 'Columns') {
            rebuiltOptions.color = draft.columnsUpColor;
        } else if (selectedStyle === 'Bars' || selectedStyle === 'HLC bars' || selectedStyle === 'High-low') {
            rebuiltOptions.upColor = draft.barsUpColor;
            rebuiltOptions.downColor = draft.barsDownColor;
            rebuiltOptions.openVisible = draft.barsOpenVisible !== false;
        }

        if (_ssIsCandleStyle(selectedStyle)) {
            var hidden = 'rgba(0, 0, 0, 0)';
            rebuiltOptions.upColor = (draft.bodyVisible !== false) ? draft.bodyUpColor : hidden;
            rebuiltOptions.downColor = (draft.bodyVisible !== false) ? draft.bodyDownColor : hidden;
            rebuiltOptions.borderUpColor = (draft.bordersVisible !== false) ? draft.borderUpColor : hidden;
            rebuiltOptions.borderDownColor = (draft.bordersVisible !== false) ? draft.borderDownColor : hidden;
            rebuiltOptions.wickUpColor = (draft.wickVisible !== false) ? draft.wickUpColor : hidden;
            rebuiltOptions.wickDownColor = (draft.wickVisible !== false) ? draft.wickDownColor : hidden;
        }

        function _ssClearStyleAux() {
            if (!entry._seriesStyleAux || !entry._seriesStyleAux[seriesId]) return;
            var aux = entry._seriesStyleAux[seriesId] || {};
            var keys = Object.keys(aux);
            for (var ai = 0; ai < keys.length; ai++) {
                var key = keys[ai];
                if (key.indexOf('series_') === 0 && aux[key] && entry.chart && typeof entry.chart.removeSeries === 'function') {
                    try { entry.chart.removeSeries(aux[key]); } catch (e) {}
                }
            }
            delete entry._seriesStyleAux[seriesId];
        }

        _ssClearStyleAux();
        rebuiltOptions = _tvMerge(rebuiltOptions, cfg.optionPatch || {});

        // Preserve current scale placement for this series
        try {
            var existingOpts = oldSeries && oldSeries.options ? oldSeries.options() : null;
            if (!_tvIsMainSeriesId(seriesId) && existingOpts && existingOpts.priceScaleId !== undefined) {
                rebuiltOptions.priceScaleId = existingOpts.priceScaleId;
            }
        } catch (e) {}

        var tickPriceFormat = _ssPriceFormatFromTick(draft.overrideMinTick);
        if (tickPriceFormat) rebuiltOptions.priceFormat = tickPriceFormat;

        // Add new series FIRST so the pane is never empty (removing the
        // last series in a pane destroys it and renumbers the rest).
        var newSeries = _tvAddSeriesCompat(entry.chart, targetType, rebuiltOptions, paneIndex);
        try { newSeries.setData(normalizedBars); } catch (e) {}
        if (oldSeries && entry.chart && typeof entry.chart.removeSeries === 'function') {
            try { entry.chart.removeSeries(oldSeries); } catch (e) {}
        }
        entry.seriesMap[seriesId] = newSeries;
        if (!entry._seriesRawData) entry._seriesRawData = {};
        entry._seriesRawData[seriesId] = normalizedBars;

        _tvUpsertPayloadSeries(entry, seriesId, {
            seriesType: targetType,
            bars: transformedRawBars,
            seriesOptions: _tvMerge((payloadSeries && payloadSeries.seriesOptions) ? payloadSeries.seriesOptions : {}, rebuiltOptions),
        });

        var legendColor = draft.color;
        if (selectedStyle === 'Columns') legendColor = draft.columnsUpColor;
        if (selectedStyle === 'Bars' || selectedStyle === 'HLC bars' || selectedStyle === 'High-low') legendColor = draft.barsUpColor;
        if (selectedStyle === 'Area') legendColor = draft.color;
        if (selectedStyle === 'Baseline') legendColor = draft.baselineTopLineColor;

        if (_ssIsHlcAreaStyle(selectedStyle)) {
            var sourceBars = Array.isArray(rawBars) ? rawBars : [];
            var highBars = [];
            var lowBars = [];
            var closeBars = [];
            for (var hi = 0; hi < sourceBars.length; hi++) {
                var r = sourceBars[hi] || {};
                if (r.time == null) continue;
                var h = _ssToNumber(r.high, _ssSourceValue(r, 'close'));
                var l = _ssToNumber(r.low, _ssSourceValue(r, 'close'));
                var c = _ssToNumber(r.close, _ssSourceValue(r, 'close'));
                highBars.push({ time: r.time, value: h });
                lowBars.push({ time: r.time, value: l });
                closeBars.push({ time: r.time, value: c });
            }
            var aux = {
                highVisible: draft.hlcHighVisible !== false,
                lowVisible: draft.hlcLowVisible !== false,
                closeVisible: draft.hlcCloseVisible !== false,
                highColor: draft.hlcHighColor,
                lowColor: draft.hlcLowColor,
                closeColor: draft.hlcCloseColor,
                fillTopColor: draft.hlcFillTopColor,
                fillBottomColor: draft.hlcFillBottomColor,
            };

            var hlcBgColor = _cssVar('--pywry-tvchart-bg');
            var hlcLineW = _tvClamp(_tvToNumber(draft.lineWidth, 1), 1, 4);
            var hlcAuxBase = {
                crosshairMarkerVisible: false,
                lastValueVisible: false,
                priceLineVisible: false,
                priceScaleId: rebuiltOptions.priceScaleId,
            };

            // Main series is the close Area (layer 3) — apply close color + fill-down
            try {
                newSeries.applyOptions({
                    topColor: draft.hlcFillBottomColor,
                    bottomColor: draft.hlcFillBottomColor,
                    lineColor: draft.hlcCloseColor,
                    lineWidth: 2,
                    visible: draft.hlcCloseVisible !== false,
                });
            } catch (e) {}

            // Layer 1: High area (fill-up color from high line down)
            var highSeries = _tvAddSeriesCompat(entry.chart, 'Area', _tvMerge(hlcAuxBase, {
                topColor: draft.hlcFillTopColor,
                bottomColor: draft.hlcFillTopColor,
                lineColor: draft.hlcHighColor,
                lineWidth: hlcLineW,
                visible: draft.hlcHighVisible !== false,
            }), paneIndex);

            // Layer 2: Close mask (opaque background erases fill-up below close)
            var closeMaskSeries = _tvAddSeriesCompat(entry.chart, 'Area', _tvMerge(hlcAuxBase, {
                topColor: hlcBgColor,
                bottomColor: hlcBgColor,
                lineColor: 'transparent',
                lineWidth: 0,
            }), paneIndex);

            // Layer 4: Low mask (opaque background erases fill-down below low + low line)
            var lowMaskSeries = _tvAddSeriesCompat(entry.chart, 'Area', _tvMerge(hlcAuxBase, {
                topColor: hlcBgColor,
                bottomColor: hlcBgColor,
                lineColor: draft.hlcLowColor,
                lineWidth: hlcLineW,
                visible: draft.hlcLowVisible !== false,
            }), paneIndex);

            try { highSeries.setData(highBars); } catch (e) {}
            try { closeMaskSeries.setData(closeBars); } catch (e) {}
            try { lowMaskSeries.setData(lowBars); } catch (e) {}

            aux.series_high = highSeries;
            aux.series_closeMask = closeMaskSeries;
            aux.series_lowMask = lowMaskSeries;
            if (!entry._seriesStyleAux) entry._seriesStyleAux = {};
            entry._seriesStyleAux[seriesId] = aux;
            if (!entry._seriesAuxRawData) entry._seriesAuxRawData = {};
            entry._seriesAuxRawData[seriesId] = { high: highBars, low: lowBars };
            legendColor = draft.hlcCloseColor;
        }

        if (!entry._seriesStylePrefs) entry._seriesStylePrefs = {};
        entry._seriesStylePrefs[seriesId] = {
            style: draft.style,
            priceSource: draft.priceSource,
            color: draft.color,
            lineWidth: draft.lineWidth,
            markersVisible: draft.markersVisible,
            areaTopColor: draft.areaTopColor,
            areaBottomColor: draft.areaBottomColor,
            baselineTopLineColor: draft.baselineTopLineColor,
            baselineBottomLineColor: draft.baselineBottomLineColor,
            baselineTopFillColor1: draft.baselineTopFillColor1,
            baselineTopFillColor2: draft.baselineTopFillColor2,
            baselineBottomFillColor1: draft.baselineBottomFillColor1,
            baselineBottomFillColor2: draft.baselineBottomFillColor2,
            baselineBaseLevel: draft.baselineBaseLevel,
            columnsUpColor: draft.columnsUpColor,
            columnsDownColor: draft.columnsDownColor,
            barsUpColor: draft.barsUpColor,
            barsDownColor: draft.barsDownColor,
            barsOpenVisible: draft.barsOpenVisible,
            bodyVisible: draft.bodyVisible,
            bordersVisible: draft.bordersVisible,
            wickVisible: draft.wickVisible,
            bodyUpColor: draft.bodyUpColor,
            bodyDownColor: draft.bodyDownColor,
            borderUpColor: draft.borderUpColor,
            borderDownColor: draft.borderDownColor,
            wickUpColor: draft.wickUpColor,
            wickDownColor: draft.wickDownColor,
            priceLineVisible: draft.priceLineVisible,
            overrideMinTick: draft.overrideMinTick,
            hlcHighVisible: draft.hlcHighVisible,
            hlcLowVisible: draft.hlcLowVisible,
            hlcCloseVisible: draft.hlcCloseVisible,
            hlcHighColor: draft.hlcHighColor,
            hlcLowColor: draft.hlcLowColor,
            hlcCloseColor: draft.hlcCloseColor,
            hlcFillTopColor: draft.hlcFillTopColor,
            hlcFillBottomColor: draft.hlcFillBottomColor,
        };
        if (!entry._legendSeriesColors) entry._legendSeriesColors = {};
        entry._legendSeriesColors[seriesId] = legendColor;
        if (!entry._seriesVisibilityIntervals) entry._seriesVisibilityIntervals = {};
        entry._seriesVisibilityIntervals[seriesId] = _tvMerge({}, draft.visibilityIntervals || {});
        _tvHideSeriesSettings();
        _tvRenderHoverLegend(chartId, null);
    });
    footer.appendChild(okBtn);
    panel.appendChild(footer);

    renderBody();
    _tvOverlayContainer(chartId).appendChild(overlay);
}

function _tvShowVolumeSettings(chartId) {
    _tvHideVolumeSettings();
    var resolved = _tvResolveChartEntry(chartId);
    if (!resolved || !resolved.entry) return;
    chartId = resolved.chartId;
    var entry = resolved.entry;
    var volSeries = entry.volumeMap && entry.volumeMap.main;
    if (!volSeries) return;

    var currentOpts = {};
    try { currentOpts = volSeries.options() || {}; } catch (e) {}
    var palette = TVCHART_THEMES._get(entry.theme || _tvDetectTheme());

    // Read persisted volume prefs or derive from current state
    var prefs = entry._volumeColorPrefs || {};
    var draft = {
        upColor: _tvColorToHex(prefs.upColor || palette.volumeUp, palette.volumeUp),
        downColor: _tvColorToHex(prefs.downColor || palette.volumeDown || palette.volumeUp, palette.volumeDown || palette.volumeUp),
        // Inputs
        maLength: prefs.maLength || 20,
        volumeMA: prefs.volumeMA || 'SMA',
        colorBasedOnPrevClose: !!prefs.colorBasedOnPrevClose,
        smoothingLine: prefs.smoothingLine || 'SMA',
        smoothingLength: prefs.smoothingLength || 9,
        // Style
        showVolume: prefs.showVolumePlot !== false,
        showVolumeMA: !!prefs.showVolumeMA,
        volumeMAColor: prefs.volumeMAColor || '#2196f3',
        showSmoothedMA: !!prefs.showSmoothedMA,
        smoothedMAColor: prefs.smoothedMAColor || '#ff6d00',
        precision: prefs.precision || 'Default',
        labelsOnPriceScale: prefs.labelsOnPriceScale !== false,
        valuesInStatusLine: prefs.valuesInStatusLine !== false,
        inputsInStatusLine: prefs.inputsInStatusLine !== false,
        priceLine: !!prefs.priceLine,
        // Visibility
        visibility: prefs.visibility || null,
    };

    // Snapshot original state for cancel/revert
    var snapshot = JSON.parse(JSON.stringify(draft));

    // --- Live preview helper: recolour volume bars immediately ---
    function applyVolumeLive() {
        var rawBars = entry._rawData;
        if (!rawBars || !Array.isArray(rawBars) || rawBars.length === 0 || !volSeries) return;
        var newVolData = [];
        for (var i = 0; i < rawBars.length; i++) {
            var b = rawBars[i];
            var v = b.volume != null ? b.volume : (b.Volume != null ? b.Volume : b.vol);
            if (v == null || isNaN(v)) continue;
            var isUp;
            if (draft.colorBasedOnPrevClose) {
                var prevClose = (i > 0) ? (rawBars[i - 1].close != null ? rawBars[i - 1].close : rawBars[i - 1].Close) : null;
                isUp = (prevClose != null && b.close != null) ? b.close >= prevClose : true;
            } else {
                isUp = (b.close != null && b.open != null) ? b.close >= b.open : true;
            }
            newVolData.push({
                time: b.time,
                value: +v,
                color: isUp ? draft.upColor : draft.downColor,
            });
        }
        if (newVolData.length > 0) volSeries.setData(newVolData);
    }

    var overlay = document.createElement('div');
    overlay.className = 'tv-settings-overlay';
    _volumeSettingsOverlay = overlay;
    _volumeSettingsOverlayChartId = chartId;
    _tvSetChartInteractionLocked(chartId, true);
    _tvRefreshLegendVisibility();
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) {
            // Revert on backdrop click
            draft = JSON.parse(JSON.stringify(snapshot));
            applyVolumeLive();
            _tvHideVolumeSettings();
        }
    });
    overlay.addEventListener('mousedown', function(e) { e.stopPropagation(); });
    overlay.addEventListener('wheel', function(e) { e.stopPropagation(); });

    var panel = document.createElement('div');
    panel.className = 'tv-settings-panel';
    panel.style.cssText = 'width:460px;max-width:calc(100% - 32px);max-height:70vh;display:flex;flex-direction:column;';
    overlay.appendChild(panel);

    // Header
    var header = document.createElement('div');
    header.className = 'tv-settings-header';
    header.style.cssText = 'position:relative;flex-direction:column;align-items:stretch;padding-bottom:0;';
    var hdrRow = document.createElement('div');
    hdrRow.style.cssText = 'display:flex;align-items:center;gap:8px;';
    var titleEl = document.createElement('h3');
    titleEl.textContent = 'Volume';
    hdrRow.appendChild(titleEl);
    var closeBtn = document.createElement('button');
    closeBtn.className = 'tv-settings-close';
    closeBtn.innerHTML = '<svg viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>';
    closeBtn.addEventListener('click', function() {
        draft = JSON.parse(JSON.stringify(snapshot));
        applyVolumeLive();
        _tvHideVolumeSettings();
    });
    hdrRow.appendChild(closeBtn);
    header.appendChild(hdrRow);

    // Tab bar
    var activeTab = 'inputs';
    var tabBar = document.createElement('div');
    tabBar.className = 'tv-ind-settings-tabs';
    var tabs = ['Inputs', 'Style', 'Visibility'];
    var tabEls = {};
    tabs.forEach(function(t) {
        var te = document.createElement('div');
        te.className = 'tv-ind-settings-tab' + (t.toLowerCase() === activeTab ? ' active' : '');
        te.textContent = t;
        te.addEventListener('click', function() {
            activeTab = t.toLowerCase();
            tabs.forEach(function(tn) { tabEls[tn].classList.toggle('active', tn.toLowerCase() === activeTab); });
            renderBody();
        });
        tabEls[t] = te;
        tabBar.appendChild(te);
    });
    header.appendChild(tabBar);
    panel.appendChild(header);

    // Body
    var body = document.createElement('div');
    body.className = 'tv-settings-body';
    body.style.cssText = 'flex:1;overflow-y:auto;min-height:80px;padding:16px 20px;';
    panel.appendChild(body);

    // --- Row builder helpers ---
    function addSection(parent, text) {
        var sec = document.createElement('div');
        sec.className = 'tv-settings-section';
        sec.textContent = text;
        parent.appendChild(sec);
    }
    function makeRow(labelText) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        var lbl = document.createElement('label');
        lbl.textContent = labelText;
        row.appendChild(lbl);
        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';
        row.appendChild(ctrl);
        return { row: row, ctrl: ctrl };
    }
    function makeColorSwatch(color, onChange) {
        var swatch = document.createElement('div');
        swatch.className = 'ts-swatch';
        swatch.dataset.baseColor = _tvColorToHex(color, '#aeb4c2');
        swatch.dataset.opacity = String(_tvColorOpacityPercent(color, 100));
        swatch.style.background = color;
        swatch.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            _tvShowColorOpacityPopup(
                swatch,
                swatch.dataset.baseColor || color,
                _tvToNumber(swatch.dataset.opacity, 100),
                overlay,
                function(newColor, newOpacity) {
                    swatch.dataset.baseColor = newColor;
                    swatch.dataset.opacity = String(newOpacity);
                    var display = _tvColorWithOpacity(newColor, newOpacity, newColor);
                    swatch.style.background = display;
                    onChange(display, newColor, newOpacity);
                }
            );
        });
        return swatch;
    }
    function addCheckRow(parent, label, val, onChange) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        var lbl = document.createElement('label'); lbl.textContent = label; row.appendChild(lbl);
        var cb = document.createElement('input'); cb.type = 'checkbox'; cb.className = 'ts-checkbox';
        cb.checked = !!val;
        cb.addEventListener('change', function() { onChange(cb.checked); });
        row.appendChild(cb); parent.appendChild(row);
    }
    function addSelectRow(parent, label, opts, val, onChange) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        var lbl = document.createElement('label'); lbl.textContent = label; row.appendChild(lbl);
        var sel = document.createElement('select'); sel.className = 'ts-select';
        opts.forEach(function(o) {
            var opt = document.createElement('option');
            opt.value = typeof o === 'string' ? o : o.v;
            opt.textContent = typeof o === 'string' ? o : o.l;
            if (String(opt.value) === String(val)) opt.selected = true;
            sel.appendChild(opt);
        });
        sel.addEventListener('change', function() { onChange(sel.value); });
        row.appendChild(sel); parent.appendChild(row);
    }
    function addNumberRow(parent, label, min, max, step, val, onChange) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        var lbl = document.createElement('label'); lbl.textContent = label; row.appendChild(lbl);
        var inp = document.createElement('input'); inp.type = 'number'; inp.className = 'ts-input';
        inp.min = min; inp.max = max; inp.step = step; inp.value = val;
        inp.addEventListener('keydown', function(e) { e.stopPropagation(); });
        inp.addEventListener('input', function() { var v = parseFloat(inp.value); if (!isNaN(v) && v >= parseFloat(min)) onChange(v); });
        row.appendChild(inp); parent.appendChild(row);
    }

    function renderBody() {
        body.innerHTML = '';

        // ===================== INPUTS TAB =====================
        if (activeTab === 'inputs') {
            // Symbol source radio buttons (separate section, no tv-settings-row label sizing)
            var symSection = document.createElement('div');
            symSection.style.cssText = 'display:flex;flex-direction:column;gap:10px;padding-bottom:12px;border-bottom:1px solid var(--pywry-tvchart-divider,rgba(128,128,128,0.15));margin-bottom:12px;';

            var r1 = document.createElement('label');
            r1.style.cssText = 'display:flex;align-items:center;gap:8px;cursor:pointer;font-size:12px;color:var(--pywry-tvchart-text);';
            var rb1 = document.createElement('input'); rb1.type = 'radio'; rb1.name = 'vol-sym-src'; rb1.value = 'main'; rb1.checked = true;
            rb1.style.cssText = 'margin:0;';
            r1.appendChild(rb1);
            r1.appendChild(document.createTextNode('Main chart symbol'));
            symSection.appendChild(r1);

            var r2 = document.createElement('label');
            r2.style.cssText = 'display:flex;align-items:center;gap:8px;cursor:default;font-size:12px;color:var(--pywry-tvchart-text-muted,#787b86);opacity:0.5;';
            var rb2 = document.createElement('input'); rb2.type = 'radio'; rb2.name = 'vol-sym-src'; rb2.value = 'other'; rb2.disabled = true;
            rb2.style.cssText = 'margin:0;';
            r2.appendChild(rb2);
            r2.appendChild(document.createTextNode('Another symbol'));
            // Pencil icon (disabled)
            var pencilSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            pencilSvg.setAttribute('viewBox', '0 0 18 18');
            pencilSvg.setAttribute('width', '14');
            pencilSvg.setAttribute('height', '14');
            pencilSvg.style.cssText = 'opacity:0.4;flex-shrink:0;';
            pencilSvg.innerHTML = '<path d="M2.5 13.5l-.5 2 2-.5L14.5 4.5l-1.5-1.5z" fill="none" stroke="currentColor" stroke-width="1.2"/>';
            r2.appendChild(pencilSvg);
            symSection.appendChild(r2);

            body.appendChild(symSection);

            // Remaining input fields
            addNumberRow(body, 'MA Length', '1', '500', '1', draft.maLength, function(v) { draft.maLength = v; });
            addSelectRow(body, 'Volume MA', [
                { v: 'SMA', l: 'SMA' }, { v: 'EMA', l: 'EMA' }, { v: 'WMA', l: 'WMA' },
            ], draft.volumeMA, function(v) { draft.volumeMA = v; });
            addCheckRow(body, 'Color based on previous close', draft.colorBasedOnPrevClose, function(v) {
                draft.colorBasedOnPrevClose = v;
                applyVolumeLive();
            });
            addSelectRow(body, 'Smoothing Line', [
                { v: 'SMA', l: 'SMA' }, { v: 'EMA', l: 'EMA' }, { v: 'WMA', l: 'WMA' },
            ], draft.smoothingLine, function(v) { draft.smoothingLine = v; });
            addNumberRow(body, 'Smoothing Length', '1', '200', '1', draft.smoothingLength, function(v) { draft.smoothingLength = v; });

        // ===================== STYLE TAB =====================
        } else if (activeTab === 'style') {
            // Volume row: checkbox + "Volume" label ... Falling swatch  Growing swatch
            var volRow = document.createElement('div');
            volRow.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:2px;';
            var volCb = document.createElement('input'); volCb.type = 'checkbox'; volCb.className = 'ts-checkbox';
            volCb.checked = draft.showVolume;
            volCb.addEventListener('change', function() { draft.showVolume = volCb.checked; });
            volRow.appendChild(volCb);
            var volLbl = document.createElement('span');
            volLbl.textContent = 'Volume';
            volLbl.style.cssText = 'font-size:12px;color:var(--pywry-tvchart-text);flex:1;';
            volRow.appendChild(volLbl);

            // Falling color group (down)
            var fallGroup = document.createElement('div');
            fallGroup.style.cssText = 'display:flex;flex-direction:column;align-items:center;gap:3px;';
            var downSwatch = makeColorSwatch(draft.downColor, function(display) {
                draft.downColor = display;
                applyVolumeLive();
            });
            fallGroup.appendChild(downSwatch);
            var fallLbl = document.createElement('span');
            fallLbl.textContent = 'Falling';
            fallLbl.style.cssText = 'font-size:10px;color:var(--pywry-tvchart-text-muted,#787b86);';
            fallGroup.appendChild(fallLbl);
            volRow.appendChild(fallGroup);

            // Growing color group (up)
            var growGroup = document.createElement('div');
            growGroup.style.cssText = 'display:flex;flex-direction:column;align-items:center;gap:3px;';
            var upSwatch = makeColorSwatch(draft.upColor, function(display) {
                draft.upColor = display;
                applyVolumeLive();
            });
            growGroup.appendChild(upSwatch);
            var growLbl = document.createElement('span');
            growLbl.textContent = 'Growing';
            growLbl.style.cssText = 'font-size:10px;color:var(--pywry-tvchart-text-muted,#787b86);';
            growGroup.appendChild(growLbl);
            volRow.appendChild(growGroup);

            body.appendChild(volRow);

            // Separator
            var sep1 = document.createElement('div');
            sep1.style.cssText = 'border-bottom:1px solid var(--pywry-tvchart-divider,rgba(128,128,128,0.15));margin:10px 0;';
            body.appendChild(sep1);

            // Price line toggle
            addCheckRow(body, 'Price line', draft.priceLine, function(v) { draft.priceLine = v; });

            // Separator
            var sep2 = document.createElement('div');
            sep2.style.cssText = 'border-bottom:1px solid var(--pywry-tvchart-divider,rgba(128,128,128,0.15));margin:10px 0;';
            body.appendChild(sep2);

            // Volume MA row: checkbox + label + color
            var maRow = document.createElement('div');
            maRow.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:8px;';
            var maCb = document.createElement('input'); maCb.type = 'checkbox'; maCb.className = 'ts-checkbox';
            maCb.checked = draft.showVolumeMA;
            maCb.addEventListener('change', function() { draft.showVolumeMA = maCb.checked; });
            maRow.appendChild(maCb);
            var maLbl = document.createElement('span');
            maLbl.textContent = 'Volume MA';
            maLbl.style.cssText = 'font-size:12px;color:var(--pywry-tvchart-text);flex:1;';
            maRow.appendChild(maLbl);
            maRow.appendChild(makeColorSwatch(draft.volumeMAColor, function(display) { draft.volumeMAColor = display; }));
            body.appendChild(maRow);

            // Smoothed MA row: checkbox + label + color
            var smRow = document.createElement('div');
            smRow.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:8px;';
            var smCb = document.createElement('input'); smCb.type = 'checkbox'; smCb.className = 'ts-checkbox';
            smCb.checked = draft.showSmoothedMA;
            smCb.addEventListener('change', function() { draft.showSmoothedMA = smCb.checked; });
            smRow.appendChild(smCb);
            var smLbl = document.createElement('span');
            smLbl.textContent = 'Smoothed MA';
            smLbl.style.cssText = 'font-size:12px;color:var(--pywry-tvchart-text);flex:1;';
            smRow.appendChild(smLbl);
            smRow.appendChild(makeColorSwatch(draft.smoothedMAColor, function(display) { draft.smoothedMAColor = display; }));
            body.appendChild(smRow);

            // Separator
            var sep3 = document.createElement('div');
            sep3.style.cssText = 'border-bottom:1px solid var(--pywry-tvchart-divider,rgba(128,128,128,0.15));margin:10px 0;';
            body.appendChild(sep3);

            // OUTPUT VALUES section
            addSection(body, 'OUTPUT VALUES');
            addSelectRow(body, 'Precision', [
                { v: 'Default', l: 'Default' }, { v: '0', l: '0' }, { v: '1', l: '1' },
                { v: '2', l: '2' }, { v: '3', l: '3' }, { v: '4', l: '4' },
            ], draft.precision, function(v) { draft.precision = v; });
            addCheckRow(body, 'Labels on price scale', draft.labelsOnPriceScale, function(v) { draft.labelsOnPriceScale = v; });
            addCheckRow(body, 'Values in status line', draft.valuesInStatusLine, function(v) { draft.valuesInStatusLine = v; });

            // INPUT VALUES section
            addSection(body, 'INPUT VALUES');
            addCheckRow(body, 'Inputs in status line', draft.inputsInStatusLine, function(v) { draft.inputsInStatusLine = v; });

        // ===================== VISIBILITY TAB =====================
        } else if (activeTab === 'visibility') {
            addSection(body, 'TIMEFRAME VISIBILITY');
            var intervals = [
                { key: 'seconds', label: 'Seconds', rangeLabel: '1s \u2013 59s' },
                { key: 'minutes', label: 'Minutes', rangeLabel: '1m \u2013 59m' },
                { key: 'hours', label: 'Hours', rangeLabel: '1H \u2013 24H' },
                { key: 'days', label: 'Days', rangeLabel: '1D \u2013 1Y' },
                { key: 'weeks', label: 'Weeks', rangeLabel: '1W \u2013 52W' },
                { key: 'months', label: 'Months', rangeLabel: '1M \u2013 12M' },
            ];
            if (!draft.visibility) {
                draft.visibility = {};
                intervals.forEach(function(iv) { draft.visibility[iv.key] = true; });
            }
            intervals.forEach(function(iv) {
                var row = document.createElement('div');
                row.className = 'tv-settings-row tv-settings-row-spaced';
                row.style.cssText = 'display:flex;align-items:center;gap:8px;';
                var cb = document.createElement('input'); cb.type = 'checkbox'; cb.className = 'ts-checkbox';
                cb.checked = draft.visibility[iv.key] !== false;
                cb.addEventListener('change', function() { draft.visibility[iv.key] = cb.checked; });
                row.appendChild(cb);
                var lbl = document.createElement('label'); lbl.style.flex = '1';
                lbl.textContent = iv.label;
                row.appendChild(lbl);
                var range = document.createElement('span');
                range.style.cssText = 'color:var(--pywry-tvchart-text-muted,#787b86);font-size:11px;';
                range.textContent = iv.rangeLabel;
                row.appendChild(range);
                body.appendChild(row);
            });
        }
    }

    renderBody();

    // Footer with Defaults dropdown, Cancel, Ok
    var footer = document.createElement('div');
    footer.className = 'tv-settings-footer';
    footer.style.cssText = 'position:relative;bottom:auto;left:auto;right:auto;';

    var cancelBtn = document.createElement('button');
    cancelBtn.className = 'ts-btn-cancel';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.addEventListener('click', function() {
        draft = JSON.parse(JSON.stringify(snapshot));
        applyVolumeLive();
        _tvHideVolumeSettings();
    });
    footer.appendChild(cancelBtn);

    var okBtn = document.createElement('button');
    okBtn.className = 'ts-btn-ok';
    okBtn.textContent = 'Ok';
    okBtn.addEventListener('click', function() {
        // Persist all volume prefs
        if (!entry._volumeColorPrefs) entry._volumeColorPrefs = {};
        entry._volumeColorPrefs.upColor = draft.upColor;
        entry._volumeColorPrefs.downColor = draft.downColor;
        entry._volumeColorPrefs.maLength = draft.maLength;
        entry._volumeColorPrefs.volumeMA = draft.volumeMA;
        entry._volumeColorPrefs.colorBasedOnPrevClose = draft.colorBasedOnPrevClose;
        entry._volumeColorPrefs.smoothingLine = draft.smoothingLine;
        entry._volumeColorPrefs.smoothingLength = draft.smoothingLength;
        entry._volumeColorPrefs.showVolumePlot = draft.showVolume;
        entry._volumeColorPrefs.showVolumeMA = draft.showVolumeMA;
        entry._volumeColorPrefs.volumeMAColor = draft.volumeMAColor;
        entry._volumeColorPrefs.showSmoothedMA = draft.showSmoothedMA;
        entry._volumeColorPrefs.smoothedMAColor = draft.smoothedMAColor;
        entry._volumeColorPrefs.precision = draft.precision;
        entry._volumeColorPrefs.labelsOnPriceScale = draft.labelsOnPriceScale;
        entry._volumeColorPrefs.valuesInStatusLine = draft.valuesInStatusLine;
        entry._volumeColorPrefs.inputsInStatusLine = draft.inputsInStatusLine;
        entry._volumeColorPrefs.priceLine = draft.priceLine;
        entry._volumeColorPrefs.visibility = draft.visibility;

        // Apply live colour change (already previewed) and update series options
        applyVolumeLive();
        if (volSeries) {
            try {
                volSeries.applyOptions({
                    lastValueVisible: draft.priceLine,
                    priceLineVisible: draft.priceLine,
                });
            } catch (e) {}
        }

        _tvHideVolumeSettings();
    });
    footer.appendChild(okBtn);
    panel.appendChild(footer);

    _tvOverlayContainer(chartId).appendChild(overlay);
}

function _tvShowChartSettings(chartId) {
    _tvHideChartSettings();
    var resolved = _tvResolveChartEntry(chartId);
    if (!resolved || !resolved.entry) return;
    chartId = resolved.chartId;
    var entry = resolved.entry;
    var currentSettings = (entry && entry._chartPrefs && entry._chartPrefs.settings)
        ? entry._chartPrefs.settings
        : _tvBuildCurrentSettings(entry);

    var overlay = document.createElement('div');
    overlay.className = 'tv-settings-overlay';
    _chartSettingsOverlay = overlay;
    _chartSettingsOverlayChartId = chartId;
    _tvSetChartInteractionLocked(chartId, true);
    _tvRefreshLegendVisibility();
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) _tvHideChartSettings();
    });
    overlay.addEventListener('mousedown', function(e) { e.stopPropagation(); });
    overlay.addEventListener('wheel', function(e) { e.stopPropagation(); });

    var panel = document.createElement('div');
    panel.className = 'tv-settings-panel';
    overlay.appendChild(panel);

    // Header (stays fixed at top)
    var header = document.createElement('div');
    header.className = 'tv-settings-header';
    var title = document.createElement('h3');
    title.textContent = 'Symbol Settings';
    header.appendChild(title);
    var closeBtn = document.createElement('button');
    closeBtn.className = 'tv-settings-close';
    closeBtn.innerHTML = '<svg viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>';
    closeBtn.addEventListener('click', function() { _tvHideChartSettings(); });
    header.appendChild(closeBtn);
    panel.appendChild(header);

    // Sidebar with tabs
    var sidebar = document.createElement('div');
    sidebar.className = 'tv-settings-sidebar';
    panel.appendChild(sidebar);

    var tabDefs = [
        { id: 'symbol', label: 'Symbol', icon: '🔤' },
        { id: 'status', label: 'Status line', icon: '━' },
        { id: 'scales', label: 'Scales and lines', icon: '↕' },
        { id: 'canvas', label: 'Canvas', icon: '⬜' }
    ];

    var tabButtons = {};
    var activeTab = 'symbol';

    for (var ti = 0; ti < tabDefs.length; ti++) {
        var tdef = tabDefs[ti];
        var tBtn = document.createElement('div');
        tBtn.className = 'tv-settings-sidebar-tab' + (ti === 0 ? ' active' : '');
        tBtn.textContent = tdef.label;
        tBtn.setAttribute('data-tab', tdef.id);
        tabButtons[tdef.id] = tBtn;
        
        (function(tabId, btn) {
            btn.addEventListener('click', function() {
                if (activeTab === tabId) return;
                tabButtons[activeTab].classList.remove('active');
                document.getElementById('pane-' + activeTab).classList.remove('active');
                tabButtons[tabId].classList.add('active');
                document.getElementById('pane-' + tabId).classList.add('active');
                activeTab = tabId;
            });
        })(tdef.id, tBtn);
        
        sidebar.appendChild(tBtn);
    }

    // Content area
    var content = document.createElement('div');
    content.className = 'tv-settings-content';
    panel.appendChild(content);

    // Helper functions for controls

    function syncSettingsSwatch(swatch, baseColor, opacityPercent) {
        if (!swatch) return;
        var nextColor = _tvColorToHex(baseColor || swatch.dataset.baseColor || '#aeb4c2', '#aeb4c2');
        var nextOpacity = _tvClamp(_tvToNumber(opacityPercent, swatch.dataset.opacity || 100), 0, 100);
        swatch.dataset.baseColor = nextColor;
        swatch.dataset.opacity = String(nextOpacity);
        swatch.style.background = _tvColorWithOpacity(nextColor, nextOpacity, nextColor);
    }

    function addCheckboxRow(parent, label, checked) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        var lbl = document.createElement('label');
        lbl.textContent = label;
        row.appendChild(lbl);
        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'ts-checkbox';
        cb.checked = !!checked;
        cb.setAttribute('data-setting', label);
        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';
        ctrl.appendChild(cb);
        row.appendChild(ctrl);
        parent.appendChild(row);
        return cb;
    }

    function addIndentedCheckboxRow(parent, label, checked) {
        var cb = addCheckboxRow(parent, label, checked);
        if (cb && cb.parentNode && cb.parentNode.parentNode) {
            cb.parentNode.parentNode.classList.add('tv-settings-row-indent');
        }
        return cb;
    }

    function addSelectRow(parent, label, options, selected) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        var lbl = document.createElement('label');
        lbl.textContent = label;
        row.appendChild(lbl);
        var sel = document.createElement('select');
        sel.className = 'ts-select';
        sel.setAttribute('data-setting', label);
        for (var i = 0; i < options.length; i++) {
            var o = document.createElement('option');
            o.value = options[i];
            o.textContent = options[i];
            if (options[i] === selected) o.selected = true;
            sel.appendChild(o);
        }
        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';
        ctrl.appendChild(sel);
        row.appendChild(ctrl);
        parent.appendChild(row);
        return sel;
    }

    function addColorRow(parent, label, checked, color) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        var lbl = document.createElement('label');
        lbl.className = 'tv-settings-inline-label';
        lbl.textContent = label;
        row.appendChild(lbl);
        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';
        if (checked != null) {
            var cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.className = 'ts-checkbox';
            cb.setAttribute('data-setting', label + '-Enabled');
            cb.checked = !!checked;
            ctrl.appendChild(cb);
        }
        var swatch = document.createElement('div');
        swatch.className = 'ts-swatch';
        swatch.setAttribute('data-setting', label + '-Color');
        swatch.dataset.baseColor = _tvColorToHex(color || '#aeb4c2', '#aeb4c2');
        swatch.dataset.opacity = String(_tvColorOpacityPercent(color, 100));
        swatch.style.background = color || '#aeb4c2';
        ctrl.appendChild(swatch);

        swatch.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            _tvShowColorOpacityPopup(
                swatch,
                swatch.dataset.baseColor || color || '#aeb4c2',
                _tvToNumber(swatch.dataset.opacity, 100),
                overlay,
                function(newColor, newOpacity) {
                    swatch.dataset.baseColor = newColor;
                    swatch.dataset.opacity = String(newOpacity);
                    swatch.style.background = _tvColorWithOpacity(newColor, newOpacity, newColor);
                    scheduleSettingsPreview();
                }
            );
        });

        row.appendChild(ctrl);
        parent.appendChild(row);
        return {
            checkbox: checked !== undefined && checked !== false ? ctrl.querySelector('input[type="checkbox"]') : null,
            swatch: swatch,
        };
    }

    function addDualColorRow(parent, label, checked, upColor, downColor, upSetting, downSetting) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';

        var lbl = document.createElement('label');
        lbl.className = 'tv-settings-inline-label';
        lbl.textContent = label;
        row.appendChild(lbl);

        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';

        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'ts-checkbox';
        cb.setAttribute('data-setting', label);
        cb.checked = !!checked;
        ctrl.appendChild(cb);

        function makeSwatch(settingKey, color) {
            var wrap = document.createElement('div');
            wrap.className = 'tv-settings-color-pair';

            var opacityInput = document.createElement('input');
            opacityInput.type = 'hidden';
            var explicitOpacity = currentSettings[settingKey + '-Opacity'];
            var legacyOpacity = currentSettings[label + '-Opacity'];
            opacityInput.value = explicitOpacity != null ? String(explicitOpacity) : (legacyOpacity != null ? String(legacyOpacity) : '100');
            opacityInput.setAttribute('data-setting', settingKey + '-Opacity');
            wrap.appendChild(opacityInput);

            var swatch = document.createElement('div');
            swatch.className = 'ts-swatch';
            swatch.setAttribute('data-setting', settingKey);
            syncSettingsSwatch(swatch, color || '#aeb4c2', opacityInput.value);
            wrap.appendChild(swatch);

            swatch.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                _tvShowColorOpacityPopup(
                    swatch,
                    swatch.dataset.baseColor || color || '#aeb4c2',
                    _tvToNumber(opacityInput.value, 100),
                    overlay,
                    function(newColor, newOpacity) {
                        opacityInput.value = String(newOpacity);
                        syncSettingsSwatch(swatch, newColor, newOpacity);
                        scheduleSettingsPreview();
                    }
                );
            });

            return wrap;
        }

        ctrl.appendChild(makeSwatch(upSetting, upColor));
        ctrl.appendChild(makeSwatch(downSetting, downColor));
        row.appendChild(ctrl);
        parent.appendChild(row);
        return row;
    }

    function addCheckboxSliderRow(parent, label, checked, enabledSetting, sliderValue, sliderSetting) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';

        var lbl = document.createElement('label');
        lbl.textContent = label;
        row.appendChild(lbl);

        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls ts-controls-slider';

        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'ts-checkbox';
        cb.checked = !!checked;
        cb.setAttribute('data-setting', enabledSetting);
        ctrl.appendChild(cb);

        var slider = document.createElement('input');
        slider.type = 'range';
        slider.min = '0';
        slider.max = '100';
        slider.value = sliderValue != null ? String(sliderValue) : '100';
        slider.className = 'tv-settings-slider';
        slider.setAttribute('data-setting', sliderSetting);
        ctrl.appendChild(slider);

        var output = document.createElement('span');
        output.className = 'tv-settings-slider-value';
        output.textContent = slider.value + '%';
        ctrl.appendChild(output);

        slider.addEventListener('input', function() {
            output.textContent = slider.value + '%';
        });

        row.appendChild(ctrl);
        parent.appendChild(row);
        return { checkbox: cb, slider: slider, output: output };
    }

    function addCheckboxInputRow(parent, label, checked, enabledSetting, inputValue, inputSetting) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced tv-settings-row-combo';

        var lbl = document.createElement('label');
        lbl.textContent = '';
        row.appendChild(lbl);

        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';

        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'ts-checkbox';
        cb.checked = !!checked;
        cb.setAttribute('data-setting', enabledSetting);
        ctrl.appendChild(cb);

        var textLbl = document.createElement('span');
        textLbl.className = 'tv-settings-inline-gap';
        textLbl.textContent = label;
        ctrl.appendChild(textLbl);

        var inp = document.createElement('input');
        inp.type = 'text';
        inp.className = 'ts-input ts-input-wide';
        inp.setAttribute('data-setting', inputSetting);
        inp.value = inputValue != null ? String(inputValue) : '';
        ctrl.appendChild(inp);

        row.appendChild(ctrl);
        parent.appendChild(row);
        return { checkbox: cb, input: inp };
    }

    function addSelectColorRow(parent, label, options, selected, selectSetting, color, colorSetting) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';

        var lbl = document.createElement('label');
        lbl.textContent = label;
        row.appendChild(lbl);

        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';

        var sel = document.createElement('select');
        sel.className = 'ts-select';
        sel.setAttribute('data-setting', selectSetting || label);
        options.forEach(function(opt) {
            var o = document.createElement('option');
            o.value = opt;
            o.textContent = opt;
            if (opt === selected) o.selected = true;
            sel.appendChild(o);
        });
        ctrl.appendChild(sel);

        var swatch = document.createElement('div');
        swatch.className = 'ts-swatch';
        swatch.setAttribute('data-setting', colorSetting || (label + ' color'));
        swatch.dataset.baseColor = _tvColorToHex(color || '#aeb4c2', '#aeb4c2');
        swatch.dataset.opacity = String(_tvColorOpacityPercent(color, 100));
        swatch.style.background = color || '#aeb4c2';
        ctrl.appendChild(swatch);

        swatch.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            _tvShowColorOpacityPopup(
                swatch,
                swatch.dataset.baseColor || color || '#aeb4c2',
                _tvToNumber(swatch.dataset.opacity, 100),
                overlay,
                function(newColor, newOpacity) {
                    swatch.dataset.baseColor = newColor;
                    swatch.dataset.opacity = String(newOpacity);
                    swatch.style.background = _tvColorWithOpacity(newColor, newOpacity, newColor);
                    scheduleSettingsPreview();
                }
            );
        });

        row.appendChild(ctrl);
        parent.appendChild(row);
        return { select: sel, swatch: swatch };
    }

    function addNumberInputRow(parent, label, settingKey, value, min, max, step, unitText, inputClassName) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';

        var lbl = document.createElement('label');
        lbl.textContent = label;
        row.appendChild(lbl);

        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';

        var inp = document.createElement('input');
        inp.type = 'number';
        inp.className = inputClassName || 'ts-input';
        inp.setAttribute('data-setting', settingKey || label);
        if (min != null) inp.min = String(min);
        if (max != null) inp.max = String(max);
        if (step != null) inp.step = String(step);
        inp.value = value != null ? String(value) : '';
        ctrl.appendChild(inp);

        if (unitText) {
            var unit = document.createElement('span');
            unit.className = 'tv-settings-unit';
            unit.textContent = unitText;
            ctrl.appendChild(unit);
        }

        row.appendChild(ctrl);
        parent.appendChild(row);
        return inp;
    }

    function addColorSwatchRow(parent, label, color, settingKey) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';

        var lbl = document.createElement('label');
        lbl.textContent = label;
        row.appendChild(lbl);

        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';

        var swatch = document.createElement('div');
        swatch.className = 'ts-swatch';
        swatch.setAttribute('data-setting', settingKey || label);
        swatch.dataset.baseColor = _tvColorToHex(color || '#aeb4c2', '#aeb4c2');
        swatch.dataset.opacity = String(_tvColorOpacityPercent(color, 100));
        swatch.style.background = color || '#aeb4c2';
        ctrl.appendChild(swatch);

        swatch.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            _tvShowColorOpacityPopup(
                swatch,
                swatch.dataset.baseColor || color || '#aeb4c2',
                _tvToNumber(swatch.dataset.opacity, 100),
                overlay,
                function(newColor, newOpacity) {
                    swatch.dataset.baseColor = newColor;
                    swatch.dataset.opacity = String(newOpacity);
                    swatch.style.background = _tvColorWithOpacity(newColor, newOpacity, newColor);
                    scheduleSettingsPreview();
                }
            );
        });

        row.appendChild(ctrl);
        parent.appendChild(row);
        return { swatch: swatch };
    }

    // Pane: Symbol
    var paneSymbol = document.createElement('div');
    paneSymbol.id = 'pane-symbol';
    paneSymbol.className = 'tv-settings-content-pane active';
    
    var lineSection = document.createElement('div');
    lineSection.className = 'tv-settings-section-body';
    paneSymbol.appendChild(lineSection);

    var mainSeries = _tvGetMainSeries(entry);
    var seriesType = mainSeries ? _tvGuessSeriesType(mainSeries) : 'Candlestick';

    var symbolTitle = document.createElement('div');
    symbolTitle.className = 'tv-settings-title';

    if (seriesType === 'Candlestick') {
        symbolTitle.textContent = 'CANDLES';
        lineSection.appendChild(symbolTitle);
        addCheckboxRow(lineSection, 'Color bars based on previous close', currentSettings['Color bars based on previous close']);
        addDualColorRow(lineSection, 'Body', currentSettings['Body'], currentSettings['Body-Up Color'], currentSettings['Body-Down Color'], 'Body-Up Color', 'Body-Down Color');
        addDualColorRow(lineSection, 'Borders', currentSettings['Borders'], currentSettings['Borders-Up Color'], currentSettings['Borders-Down Color'], 'Borders-Up Color', 'Borders-Down Color');
        addDualColorRow(lineSection, 'Wick', currentSettings['Wick'], currentSettings['Wick-Up Color'], currentSettings['Wick-Down Color'], 'Wick-Up Color', 'Wick-Down Color');
    } else if (seriesType === 'Bar') {
        symbolTitle.textContent = 'BARS';
        lineSection.appendChild(symbolTitle);
        addCheckboxRow(lineSection, 'Color bars based on previous close', currentSettings['Color bars based on previous close']);
        addColorSwatchRow(lineSection, 'Up color', currentSettings['Bar Up Color'], 'Bar Up Color');
        addColorSwatchRow(lineSection, 'Down color', currentSettings['Bar Down Color'], 'Bar Down Color');
    } else if (seriesType === 'Line') {
        symbolTitle.textContent = 'LINE';
        lineSection.appendChild(symbolTitle);
        addColorSwatchRow(lineSection, 'Color', currentSettings['Line color'], 'Line color');
        addSelectRow(lineSection, 'Line style', ['Solid', 'Dotted', 'Dashed'], currentSettings['Line style']);
        addNumberInputRow(lineSection, 'Line width', 'Line width', currentSettings['Line width'], 1, 4, 1, '', 'ts-input');
    } else if (seriesType === 'Area') {
        symbolTitle.textContent = 'AREA';
        lineSection.appendChild(symbolTitle);
        addColorSwatchRow(lineSection, 'Line color', currentSettings['Line color'], 'Line color');
        addNumberInputRow(lineSection, 'Line width', 'Line width', currentSettings['Line width'], 1, 4, 1, '', 'ts-input');
        addColorSwatchRow(lineSection, 'Fill 1', currentSettings['Area Fill Top'], 'Area Fill Top');
        addColorSwatchRow(lineSection, 'Fill 2', currentSettings['Area Fill Bottom'], 'Area Fill Bottom');
    } else if (seriesType === 'Baseline') {
        symbolTitle.textContent = 'BASELINE';
        lineSection.appendChild(symbolTitle);
        addNumberInputRow(lineSection, 'Base level', 'Baseline Level', currentSettings['Baseline Level'], null, null, null, '', 'ts-input');
        addColorSwatchRow(lineSection, 'Top line color', currentSettings['Baseline Top Line'], 'Baseline Top Line');
        addColorSwatchRow(lineSection, 'Bottom line color', currentSettings['Baseline Bottom Line'], 'Baseline Bottom Line');
        addColorSwatchRow(lineSection, 'Top area 1', currentSettings['Baseline Top Fill 1'], 'Baseline Top Fill 1');
        addColorSwatchRow(lineSection, 'Top area 2', currentSettings['Baseline Top Fill 2'], 'Baseline Top Fill 2');
        addColorSwatchRow(lineSection, 'Bottom area 1', currentSettings['Baseline Bottom Fill 1'], 'Baseline Bottom Fill 1');
        addColorSwatchRow(lineSection, 'Bottom area 2', currentSettings['Baseline Bottom Fill 2'], 'Baseline Bottom Fill 2');
    } else if (seriesType === 'Histogram') {
        symbolTitle.textContent = 'COLUMNS';
        lineSection.appendChild(symbolTitle);
        addCheckboxRow(lineSection, 'Color bars based on previous close', currentSettings['Color bars based on previous close']);
        addColorSwatchRow(lineSection, 'Up color', currentSettings['Bar Up Color'], 'Bar Up Color');
        addColorSwatchRow(lineSection, 'Down color', currentSettings['Bar Down Color'], 'Bar Down Color');
    } else {
        symbolTitle.textContent = seriesType.toUpperCase();
        lineSection.appendChild(symbolTitle);
        addColorSwatchRow(lineSection, 'Color', currentSettings['Line color'], 'Line color');
        addNumberInputRow(lineSection, 'Line width', 'Line width', currentSettings['Line width'], 1, 4, 1, '', 'ts-input');
    }

    var modTitle = document.createElement('div');
    modTitle.className = 'tv-settings-section';
    modTitle.textContent = 'DATA MODIFICATION';
    lineSection.appendChild(modTitle);

    addSelectRow(lineSection, 'Session', ['Regular trading hours', 'Extended trading hours'], currentSettings['Session']);
    addSelectRow(lineSection, 'Precision', ['Default', '0.1', '0.01', '0.001', '0.0001'], currentSettings['Precision']);
    addSelectRow(lineSection, 'Timezone', ['UTC', 'Local'], currentSettings['Timezone']);

    // Ensure the default Symbol tab has visible content.
    content.appendChild(paneSymbol);

    // Pane: Status line
    var paneStatus = document.createElement('div');
    paneStatus.id = 'pane-status';
    paneStatus.className = 'tv-settings-content-pane';
    var statusSection = document.createElement('div');
    statusSection.className = 'tv-settings-section-body';
    paneStatus.appendChild(statusSection);
    var statusTitle = document.createElement('div');
    statusTitle.className = 'tv-settings-title';
    statusTitle.textContent = 'SYMBOL';
    statusSection.appendChild(statusTitle);

    addCheckboxRow(statusSection, 'Logo', currentSettings['Logo']);

    // Title checkbox + inline description-mode dropdown (matches TradingView layout)
    (function() {
        var row = document.createElement('div');
        row.className = 'tv-settings-row tv-settings-row-spaced';
        var lbl = document.createElement('label');
        lbl.textContent = 'Title';
        row.appendChild(lbl);
        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';
        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'ts-checkbox';
        cb.checked = currentSettings['Title'] !== false;
        cb.setAttribute('data-setting', 'Title');
        ctrl.appendChild(cb);
        var sel = document.createElement('select');
        sel.className = 'ts-select';
        sel.setAttribute('data-setting', 'Description');
        var descOpts = ['Description', 'Ticker', 'Ticker and description'];
        for (var di = 0; di < descOpts.length; di++) {
            var o = document.createElement('option');
            o.value = descOpts[di];
            o.textContent = descOpts[di];
            if (descOpts[di] === (currentSettings['Description'] || 'Description')) o.selected = true;
            sel.appendChild(o);
        }
        ctrl.appendChild(sel);
        row.appendChild(ctrl);
        statusSection.appendChild(row);
    })();
    addCheckboxRow(statusSection, 'Chart values', currentSettings['Chart values']);
    addCheckboxRow(statusSection, 'Bar change values', currentSettings['Bar change values']);
    addCheckboxRow(statusSection, 'Volume', currentSettings['Volume']);

    var statusIndicTitle = document.createElement('div');
    statusIndicTitle.className = 'tv-settings-section';
    statusIndicTitle.textContent = 'INDICATORS';
    statusSection.appendChild(statusIndicTitle);

    addCheckboxRow(statusSection, 'Titles', currentSettings['Titles']);

    addIndentedCheckboxRow(statusSection, 'Inputs', currentSettings['Inputs']);

    addCheckboxRow(statusSection, 'Values', currentSettings['Values']);
    addCheckboxSliderRow(
        statusSection,
        'Background',
        currentSettings['Background-Enabled'],
        'Background-Enabled',
        currentSettings['Background-Opacity'],
        'Background-Opacity'
    );

    content.appendChild(paneStatus);

    // Pane: Scales and lines - COMPLETE IMPLEMENTATION
    var paneScales = document.createElement('div');
    paneScales.id = 'pane-scales';
    paneScales.className = 'tv-settings-content-pane';
    var scalesSection = document.createElement('div');
    scalesSection.className = 'tv-settings-section-body';
    paneScales.appendChild(scalesSection);

    var scalePriceTitle = document.createElement('div');
    scalePriceTitle.className = 'tv-settings-section';
    scalePriceTitle.textContent = 'PRICE SCALE';
    scalesSection.appendChild(scalePriceTitle);

    addSelectRow(scalesSection, 'Scale modes (A and L)', ['Visible on mouse over', 'Hidden'], currentSettings['Scale modes (A and L)']);

    addCheckboxInputRow(
        scalesSection,
        'Lock price to bar ratio',
        currentSettings['Lock price to bar ratio'],
        'Lock price to bar ratio',
        currentSettings['Lock price to bar ratio (value)'],
        'Lock price to bar ratio (value)'
    );

    addSelectRow(scalesSection, 'Scales placement', ['Auto', 'Left', 'Right'], currentSettings['Scales placement']);

    var scalePriceLabelsTitle = document.createElement('div');
    scalePriceLabelsTitle.className = 'tv-settings-section';
    scalePriceLabelsTitle.textContent = 'PRICE LABELS & LINES';
    scalesSection.appendChild(scalePriceLabelsTitle);

    addCheckboxRow(scalesSection, 'No overlapping labels', currentSettings['No overlapping labels']);
    addCheckboxRow(scalesSection, 'Plus button', currentSettings['Plus button']);
    addCheckboxRow(scalesSection, 'Countdown to bar close', currentSettings['Countdown to bar close']);

    addSelectColorRow(
        scalesSection,
        'Symbol',
        ['Value, line', 'Line', 'Label', 'Hidden'],
        currentSettings['Symbol'],
        'Symbol',
        currentSettings['Symbol color'],
        'Symbol color'
    );

    addSelectRow(
        scalesSection,
        'Value according to scale',
        ['Value according to scale', 'Percent change'],
        currentSettings['Value according to scale'] || currentSettings['Value according to sc...']
    );
    addSelectRow(scalesSection, 'Indicators and financials', ['Value', 'Change', 'Percent change'], currentSettings['Indicators and financials']);

    addSelectColorRow(
        scalesSection,
        'High and low',
        ['Hidden', 'Values only', 'Values and lines'],
        currentSettings['High and low'],
        'High and low',
        currentSettings['High and low color'],
        'High and low color'
    );

    var scaleTimeTitle = document.createElement('div');
    scaleTimeTitle.className = 'tv-settings-section';
    scaleTimeTitle.textContent = 'TIME SCALE';
    scalesSection.appendChild(scaleTimeTitle);

    addCheckboxRow(scalesSection, 'Day of week on labels', currentSettings['Day of week on labels']);
    addSelectRow(scalesSection, 'Date format', ['Mon 29 Sep \'97', 'MM/DD/YY', 'DD/MM/YY', 'YYYY-MM-DD'], currentSettings['Date format']);
    addSelectRow(scalesSection, 'Time hours format', ['24-hours', '12-hours'], currentSettings['Time hours format']);

    content.appendChild(paneScales);

    // Pane: Canvas - COMPLETE IMPLEMENTATION
    var paneCanvas = document.createElement('div');
    paneCanvas.id = 'pane-canvas';
    paneCanvas.className = 'tv-settings-content-pane';
    var canvasSection = document.createElement('div');
    canvasSection.className = 'tv-settings-section-body';
    paneCanvas.appendChild(canvasSection);

    var canvasBasicTitle = document.createElement('div');
    canvasBasicTitle.className = 'tv-settings-section';
    canvasBasicTitle.textContent = 'CHART BASIC STYLES';
    canvasSection.appendChild(canvasBasicTitle);

    addSelectColorRow(canvasSection, 'Background', ['Solid', 'Gradient'], currentSettings['Background'], 'Background', currentSettings['Background-Color'], 'Background-Color');
    addSelectColorRow(canvasSection, 'Grid lines', ['Vert and horz', 'Vert only', 'Horz only', 'Hidden'], currentSettings['Grid lines'], 'Grid lines', currentSettings['Grid-Color'], 'Grid-Color');
    addColorSwatchRow(canvasSection, 'Pane separators', currentSettings['Pane-Separators-Color'], 'Pane-Separators-Color');
    addColorRow(canvasSection, 'Crosshair', currentSettings['Crosshair-Enabled'], currentSettings['Crosshair-Color']);
    addSelectColorRow(canvasSection, 'Watermark', ['Hidden', 'Visible'], currentSettings['Watermark'], 'Watermark', currentSettings['Watermark-Color'], 'Watermark-Color');

    var canvasScalesTitle = document.createElement('div');
    canvasScalesTitle.className = 'tv-settings-section';
    canvasScalesTitle.textContent = 'SCALES';
    canvasSection.appendChild(canvasScalesTitle);

    addColorRow(canvasSection, 'Text', null, currentSettings['Text-Color']);
    addColorRow(canvasSection, 'Lines', null, currentSettings['Lines-Color']);

    var canvasButtonsTitle = document.createElement('div');
    canvasButtonsTitle.className = 'tv-settings-section';
    canvasButtonsTitle.textContent = 'BUTTONS';
    canvasSection.appendChild(canvasButtonsTitle);

    addSelectRow(canvasSection, 'Navigation', ['Visible on mouse over', 'Hidden'], currentSettings['Navigation']);
    addSelectRow(canvasSection, 'Pane', ['Visible on mouse over', 'Hidden'], currentSettings['Pane']);

    var canvasMarginsTitle = document.createElement('div');
    canvasMarginsTitle.className = 'tv-settings-section';
    canvasMarginsTitle.textContent = 'MARGINS';
    canvasSection.appendChild(canvasMarginsTitle);

    addNumberInputRow(canvasSection, 'Top', 'Margin Top', currentSettings['Margin Top'], 0, 100, 1, '%', 'ts-input ts-input-sm');
    addNumberInputRow(canvasSection, 'Bottom', 'Margin Bottom', currentSettings['Margin Bottom'], 0, 100, 1, '%', 'ts-input ts-input-sm');

    content.appendChild(paneCanvas);

    // Footer
    var footer = document.createElement('div');
    footer.className = 'tv-settings-footer';
    var originalSettings = JSON.parse(JSON.stringify(currentSettings || {}));

    function collectSettingsFromPanel() {
        var settings = {};
        var allControls = panel.querySelectorAll('[data-setting]');
        allControls.forEach(function(ctrl) {
            var settingKey = ctrl.getAttribute('data-setting');
            if (!settingKey) return;

            var value;
            if (ctrl.tagName === 'SELECT') {
                value = ctrl.value;
            } else if (ctrl.tagName === 'INPUT') {
                if (ctrl.type === 'checkbox') {
                    value = ctrl.checked;
                } else if (ctrl.type === 'number' || ctrl.type === 'text' || ctrl.type === 'range' || ctrl.type === 'hidden') {
                    value = ctrl.value;
                }
            } else if (ctrl.classList.contains('ts-swatch')) {
                value = ctrl.style.background || ctrl.style.backgroundColor || '#aeb4c2';
            }

            if (value !== undefined) settings[settingKey] = value;
        });

        if (entry && entry._chartPrefs) {
            if (entry._chartPrefs.logScale !== undefined) settings['Log scale'] = !!entry._chartPrefs.logScale;
            if (entry._chartPrefs.autoScale !== undefined) settings['Auto Scale'] = !!entry._chartPrefs.autoScale;
        }
        return settings;
    }

    function syncLegendPreview(settings) {
        var legendBox = _tvScopedById(chartId, 'tvchart-legend-box');
        if (!legendBox) return;
        var titleVisible = settings['Title'] !== false;
        legendBox.style.color = settings['Text-Color'] || '';

        var titleNode = _tvScopedById(chartId, 'tvchart-legend-title');
        if (titleNode) titleNode.style.display = titleVisible ? 'inline-flex' : 'none';
    }

    function scheduleSettingsPreview() {
        if (!entry || !panel) return;
        try {
            var previewSettings = collectSettingsFromPanel();
            _tvApplySettingsToChart(chartId, entry, previewSettings);
            syncLegendPreview(previewSettings);
        } catch (previewErr) {
            console.warn('Settings preview error:', previewErr);
        }
    }

    function persistSettings(settings) {
        if (!entry._chartPrefs) entry._chartPrefs = {};
        entry._chartPrefs.settings = settings;
        entry._chartPrefs.colorBarsBasedOnPrevClose = !!settings['Color bars based on previous close'];
        entry._chartPrefs.bodyVisible = settings['Body'] !== false;
        entry._chartPrefs.bodyUpColor = settings['Body-Up Color'] || _cssVar('--pywry-tvchart-up', '');
        entry._chartPrefs.bodyDownColor = settings['Body-Down Color'] || _cssVar('--pywry-tvchart-down', '');
        entry._chartPrefs.bodyUpOpacity = _tvToNumber(settings['Body-Up Color-Opacity'], _tvToNumber(settings['Body-Opacity'], 100));
        entry._chartPrefs.bodyDownOpacity = _tvToNumber(settings['Body-Down Color-Opacity'], _tvToNumber(settings['Body-Opacity'], 100));
        entry._chartPrefs.bodyOpacity = _tvToNumber(settings['Body-Opacity'], 100);
        entry._chartPrefs.bordersVisible = settings['Borders'] !== false;
        entry._chartPrefs.borderUpColor = settings['Borders-Up Color'] || _cssVar('--pywry-tvchart-border-up', '');
        entry._chartPrefs.borderDownColor = settings['Borders-Down Color'] || _cssVar('--pywry-tvchart-border-down', '');
        entry._chartPrefs.borderUpOpacity = _tvToNumber(settings['Borders-Up Color-Opacity'], _tvToNumber(settings['Borders-Opacity'], 100));
        entry._chartPrefs.borderDownOpacity = _tvToNumber(settings['Borders-Down Color-Opacity'], _tvToNumber(settings['Borders-Opacity'], 100));
        entry._chartPrefs.borderOpacity = _tvToNumber(settings['Borders-Opacity'], 100);
        entry._chartPrefs.wickVisible = settings['Wick'] !== false;
        entry._chartPrefs.wickUpColor = settings['Wick-Up Color'] || _cssVar('--pywry-tvchart-wick-up', '');
        entry._chartPrefs.wickDownColor = settings['Wick-Down Color'] || _cssVar('--pywry-tvchart-wick-down', '');
        entry._chartPrefs.wickUpOpacity = _tvToNumber(settings['Wick-Up Color-Opacity'], _tvToNumber(settings['Wick-Opacity'], 100));
        entry._chartPrefs.wickDownOpacity = _tvToNumber(settings['Wick-Down Color-Opacity'], _tvToNumber(settings['Wick-Opacity'], 100));
        entry._chartPrefs.wickOpacity = _tvToNumber(settings['Wick-Opacity'], 100);
        // Bar-specific
        entry._chartPrefs.barUpColor = settings['Bar Up Color'] || '';
        entry._chartPrefs.barDownColor = settings['Bar Down Color'] || '';
        // Area-specific
        entry._chartPrefs.areaFillTop = settings['Area Fill Top'] || '';
        entry._chartPrefs.areaFillBottom = settings['Area Fill Bottom'] || '';
        // Baseline-specific
        entry._chartPrefs.baselineLevel = _tvToNumber(settings['Baseline Level'], 0);
        entry._chartPrefs.baselineTopLine = settings['Baseline Top Line'] || '';
        entry._chartPrefs.baselineBottomLine = settings['Baseline Bottom Line'] || '';
        entry._chartPrefs.baselineTopFill1 = settings['Baseline Top Fill 1'] || '';
        entry._chartPrefs.baselineTopFill2 = settings['Baseline Top Fill 2'] || '';
        entry._chartPrefs.baselineBottomFill1 = settings['Baseline Bottom Fill 1'] || '';
        entry._chartPrefs.baselineBottomFill2 = settings['Baseline Bottom Fill 2'] || '';
        entry._chartPrefs.session = settings['Session'] || 'Regular trading hours';
        entry._chartPrefs.precision = settings['Precision'] || 'Default';
        entry._chartPrefs.timezone = settings['Timezone'] || 'UTC';
        entry._chartPrefs.description = settings['Description'] || 'Description';
        entry._chartPrefs.showLogo = settings['Logo'] !== false;
        entry._chartPrefs.showTitle = settings['Title'] !== false;
        entry._chartPrefs.showChartValues = settings['Chart values'] !== false;
        entry._chartPrefs.showBarChange = settings['Bar change values'] !== false;
        entry._chartPrefs.showVolume = settings['Volume'] !== false;
        entry._chartPrefs.showIndicatorTitles = settings['Titles'] !== false;
        entry._chartPrefs.showIndicatorInputs = settings['Inputs'] !== false;
        entry._chartPrefs.showIndicatorValues = settings['Values'] !== false;
        if (settings['Log scale'] !== undefined) entry._chartPrefs.logScale = !!settings['Log scale'];
        if (settings['Auto Scale'] !== undefined) entry._chartPrefs.autoScale = !!settings['Auto Scale'];
        entry._chartPrefs.backgroundEnabled = settings['Background-Enabled'] !== false;
        entry._chartPrefs.backgroundOpacity = _tvToNumber(settings['Background-Opacity'], 50);
        entry._chartPrefs.lineColor = settings['Line color'] || _cssVar('--pywry-tvchart-up', '');
        entry._chartPrefs.scaleModesVisibility = settings['Scale modes (A and L)'] || 'Visible on mouse over';
        entry._chartPrefs.lockPriceToBarRatio = !!settings['Lock price to bar ratio'];
        entry._chartPrefs.lockPriceToBarRatioValue = _tvToNumber(settings['Lock price to bar ratio (value)'], 0.018734);
        entry._chartPrefs.scalesPlacement = settings['Scales placement'] || 'Auto';
        entry._chartPrefs.noOverlappingLabels = settings['No overlapping labels'] !== false;
        entry._chartPrefs.plusButton = !!settings['Plus button'];
        entry._chartPrefs.countdownToBarClose = !!settings['Countdown to bar close'];
        entry._chartPrefs.symbolMode = settings['Symbol'] || 'Value, line';
        entry._chartPrefs.symbolColor = settings['Symbol color'] || _cssVar('--pywry-tvchart-up', '');
        entry._chartPrefs.valueAccordingToScale = settings['Value according to scale'] || settings['Value according to sc...'] || 'Value according to scale';
        entry._chartPrefs.indicatorsAndFinancials = settings['Indicators and financials'] || 'Value';
        entry._chartPrefs.highAndLow = settings['High and low'] || 'Hidden';
        entry._chartPrefs.highAndLowColor = settings['High and low color'] || _cssVar('--pywry-tvchart-down');
        entry._chartPrefs.dayOfWeekOnLabels = settings['Day of week on labels'] !== false;
        entry._chartPrefs.dateFormat = settings['Date format'] || 'Mon 29 Sep \'97';
        entry._chartPrefs.timeHoursFormat = settings['Time hours format'] || '24-hours';
        entry._chartPrefs.gridVisible = settings['Grid lines'] !== 'Hidden';
        entry._chartPrefs.gridMode = settings['Grid lines'] || 'Vert and horz';
        entry._chartPrefs.gridColor = settings['Grid-Color'] || _cssVar('--pywry-tvchart-grid');
        entry._chartPrefs.paneSeparatorsColor = settings['Pane-Separators-Color'] || _cssVar('--pywry-tvchart-grid');
        entry._chartPrefs.backgroundColor = settings['Background-Color'] || _cssVar('--pywry-tvchart-bg');
        entry._chartPrefs.crosshairEnabled = settings['Crosshair-Enabled'] === true;
        entry._chartPrefs.crosshairColor = settings['Crosshair-Color'] || _cssVar('--pywry-tvchart-crosshair-color');
        entry._chartPrefs.watermarkVisible = settings['Watermark'] === 'Visible';
        entry._chartPrefs.watermarkColor = settings['Watermark-Color'] || 'rgba(255,255,255,0.08)';
        entry._chartPrefs.textColor = settings['Text-Color'] || _cssVar('--pywry-tvchart-text');
        entry._chartPrefs.linesColor = settings['Lines-Color'] || _cssVar('--pywry-tvchart-grid');
        entry._chartPrefs.navigation = settings['Navigation'] || 'Visible on mouse over';
        entry._chartPrefs.pane = settings['Pane'] || 'Visible on mouse over';
        entry._chartPrefs.marginTop = _tvToNumber(settings['Margin Top'], 10);
        entry._chartPrefs.marginBottom = _tvToNumber(settings['Margin Bottom'], 8);
    }

    function applySettingsToPanel(nextSettings) {
        if (!panel || !nextSettings || typeof nextSettings !== 'object') return;

        var allControls = panel.querySelectorAll('[data-setting]');
        allControls.forEach(function(ctrl) {
            var key = ctrl.getAttribute('data-setting');
            if (!key || nextSettings[key] === undefined) return;
            var value = nextSettings[key];
            if (ctrl.tagName === 'SELECT') {
                ctrl.value = String(value);
            } else if (ctrl.tagName === 'INPUT') {
                if (ctrl.type === 'checkbox') {
                    ctrl.checked = !!value;
                } else {
                    ctrl.value = String(value);
                }
            }
        });

        var swatches = panel.querySelectorAll('.ts-swatch[data-setting]');
        swatches.forEach(function(swatch) {
            var key = swatch.getAttribute('data-setting');
            if (!key || nextSettings[key] === undefined) return;
            var colorVal = nextSettings[key];
            var opacityKey = key + '-Opacity';
            if (nextSettings[opacityKey] !== undefined) {
                syncSettingsSwatch(swatch, colorVal, nextSettings[opacityKey]);
            } else {
                var nextHex = _tvColorToHex(colorVal || swatch.style.background || '#aeb4c2', '#aeb4c2');
                swatch.dataset.baseColor = nextHex;
                swatch.style.background = nextHex;
            }

            var swParent = swatch.parentNode;
            if (swParent && swParent.querySelector) {
                var colorInput = swParent.querySelector('input.ts-hidden-color-input[type="color"]');
                if (colorInput) {
                    colorInput.value = _tvColorToHex(swatch.dataset.baseColor || swatch.style.background, '#aeb4c2');
                }
            }
        });

        var sliders = panel.querySelectorAll('.tv-settings-slider');
        sliders.forEach(function(slider) {
            var out = slider.parentNode && slider.parentNode.querySelector('.tv-settings-slider-value');
            if (out) out.textContent = slider.value + '%';
        });

        scheduleSettingsPreview();
    }

    var factoryTemplate = _tvBuildCurrentSettings({
        chartId: chartId,
        theme: entry && entry.theme,
        _chartPrefs: {},
        volumeMap: (entry && entry.volumeMap && entry.volumeMap.main) ? { main: {} } : {},
        seriesMap: {},
    });

    function cloneSettings(settingsObj) {
        try {
            return JSON.parse(JSON.stringify(settingsObj || {}));
        } catch (e) {
            return {};
        }
    }

    function getResolvedTemplateId() {
        var preferred = _tvLoadSettingsDefaultTemplateId(chartId);
        if (preferred === 'custom' && !_tvLoadCustomSettingsTemplate(chartId)) {
            _tvSaveSettingsDefaultTemplateId('factory', chartId);
            return 'factory';
        }
        return preferred;
    }
    
    var templateWrap = document.createElement('div');
    templateWrap.className = 'tv-settings-template-wrap';
    var templateBtn = document.createElement('button');
    templateBtn.className = 'ts-btn-template';
    templateBtn.type = 'button';
    templateBtn.textContent = 'Template';
    templateWrap.appendChild(templateBtn);

    var templateMenu = null;

    function closeTemplateMenu() {
        if (templateMenu && templateMenu.parentNode) {
            templateMenu.parentNode.removeChild(templateMenu);
        }
        templateMenu = null;
    }

    function updateTemplateDefaultBadges(menuEl) {
        if (!menuEl) return;
        var activeId = getResolvedTemplateId();
        var defaultItems = menuEl.querySelectorAll('.tv-settings-template-item[data-template-default]');
        defaultItems.forEach(function(item) {
            var itemId = item.getAttribute('data-template-default');
            var isActive = itemId === activeId;
            item.classList.toggle('active-default', isActive);
            var badge = item.querySelector('.tv-settings-template-badge');
            if (badge) badge.style.visibility = isActive ? 'visible' : 'hidden';
        });
    }

    function openTemplateMenu() {
        closeTemplateMenu();
        var customTemplate = _tvLoadCustomSettingsTemplate(chartId);
        var activeDefaultId = getResolvedTemplateId();

        var menu = document.createElement('div');
        menu.className = 'tv-settings-template-menu';

        var applyItem = document.createElement('button');
        applyItem.type = 'button';
        applyItem.className = 'tv-settings-template-item';
        applyItem.textContent = 'Apply default template';
        applyItem.addEventListener('click', function() {
            var resolvedDefault = getResolvedTemplateId();
            var chosen = resolvedDefault === 'custom' ? (_tvLoadCustomSettingsTemplate(chartId) || factoryTemplate) : factoryTemplate;
            applySettingsToPanel(cloneSettings(chosen));
            _tvNotify('success', 'Template applied.', 'Settings', chartId);
            closeTemplateMenu();
        });
        menu.appendChild(applyItem);

        var sep = document.createElement('div');
        sep.className = 'tv-settings-template-sep';
        menu.appendChild(sep);

        function makeDefaultItem(label, templateId, disabled) {
            var item = document.createElement('button');
            item.type = 'button';
            item.className = 'tv-settings-template-item';
            item.setAttribute('data-template-default', templateId);
            if (disabled) item.disabled = true;
            var text = document.createElement('span');
            text.textContent = label;
            item.appendChild(text);
            var badge = document.createElement('span');
            badge.className = 'tv-settings-template-badge';
            badge.textContent = 'default';
            badge.style.visibility = templateId === activeDefaultId ? 'visible' : 'hidden';
            item.appendChild(badge);
            item.addEventListener('click', function() {
                _tvSaveSettingsDefaultTemplateId(templateId, chartId);
                updateTemplateDefaultBadges(menu);
            });
            return item;
        }

        menu.appendChild(makeDefaultItem('Use TradingView defaults', 'factory', false));
        menu.appendChild(makeDefaultItem('Use saved custom default', 'custom', !customTemplate));

        var saveCurrent = document.createElement('button');
        saveCurrent.type = 'button';
        saveCurrent.className = 'tv-settings-template-item';
        saveCurrent.textContent = 'Save current as custom default';
        saveCurrent.addEventListener('click', function() {
            var settings = collectSettingsFromPanel();
            _tvSaveCustomSettingsTemplate(cloneSettings(settings), chartId);
            _tvSaveSettingsDefaultTemplateId('custom', chartId);
            updateTemplateDefaultBadges(menu);
            var customDefaultRow = menu.querySelector('[data-template-default="custom"]');
            if (customDefaultRow) customDefaultRow.disabled = false;
            _tvNotify('success', 'Saved custom default template.', 'Settings', chartId);
        });
        menu.appendChild(saveCurrent);

        var clearCustom = document.createElement('button');
        clearCustom.type = 'button';
        clearCustom.className = 'tv-settings-template-item';
        clearCustom.textContent = 'Clear custom default';
        clearCustom.disabled = !customTemplate;
        clearCustom.addEventListener('click', function() {
            _tvClearCustomSettingsTemplate(chartId);
            if (_tvLoadSettingsDefaultTemplateId(chartId) === 'custom') {
                _tvSaveSettingsDefaultTemplateId('factory', chartId);
            }
            var customDefaultRow = menu.querySelector('[data-template-default="custom"]');
            if (customDefaultRow) customDefaultRow.disabled = true;
            clearCustom.disabled = true;
            updateTemplateDefaultBadges(menu);
            _tvNotify('success', 'Cleared custom default template.', 'Settings', chartId);
        });
        menu.appendChild(clearCustom);

        templateMenu = menu;
        templateWrap.appendChild(menu);
        updateTemplateDefaultBadges(menu);
    }

    templateBtn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        if (templateMenu) {
            closeTemplateMenu();
        } else {
            openTemplateMenu();
        }
    });

    overlay.addEventListener('mousedown', function(e) {
        if (templateMenu && templateWrap && !templateWrap.contains(e.target)) {
            closeTemplateMenu();
        }
    });

    footer.appendChild(templateWrap);

    var cancelBtn = document.createElement('button');
    cancelBtn.className = 'ts-btn-cancel';
    cancelBtn.addEventListener('click', function() {
        closeTemplateMenu();
        _tvApplySettingsToChart(chartId, entry, originalSettings);
        syncLegendPreview(originalSettings);
        _tvHideChartSettings();
    });
    cancelBtn.textContent = 'Cancel';
    footer.appendChild(cancelBtn);

    var okBtn = document.createElement('button');
    okBtn.className = 'ts-btn-ok';
    okBtn.addEventListener('click', function() {
        if (!entry || !panel) return;
        try {
            closeTemplateMenu();
            var settings = collectSettingsFromPanel();
            persistSettings(settings);
            _tvApplySettingsToChart(chartId, entry, settings);
            syncLegendPreview(settings);

            // Sync session mode from chart settings to bottom bar
            var sessionSetting = settings['Session'] || 'Extended trading hours';
            var newMode = sessionSetting.indexOf('Regular') >= 0 ? 'RTH' : 'ETH';
            if (entry._sessionMode !== newMode) {
                entry._sessionMode = newMode;
                var sBtn = document.getElementById('tvchart-session-btn');
                if (sBtn) {
                    var sLbl = sBtn.querySelector('.tvchart-bottom-btn-label');
                    if (sLbl) sLbl.textContent = newMode;
                    sBtn.classList.toggle('active', newMode === 'RTH');
                }
            }

            // Re-apply bottom bar timezone (takes precedence over chart settings' UTC/Local)
            if (typeof _tvGetActiveTimezone === 'function' && typeof _tvApplyTimezoneToChart === 'function') {
                var activeTz = _tvGetActiveTimezone();
                if (entry._selectedTimezone && entry._selectedTimezone !== 'exchange') {
                    _tvApplyTimezoneToChart(entry, activeTz);
                }
            }

            console.log('Chart settings applied:', settings);
        } catch(err) {
            console.warn('Settings apply error:', err);
        }
        _tvHideChartSettings();
    });
    okBtn.textContent = 'Ok';
    footer.appendChild(okBtn);

    panel.appendChild(footer);
    panel.addEventListener('input', function(e) {
        var target = e.target;
        if (!target) return;
        if (target.tagName === 'INPUT' || target.tagName === 'SELECT') scheduleSettingsPreview();
    });
    panel.addEventListener('change', function(e) {
        var target = e.target;
        if (!target) return;
        if (target.tagName === 'INPUT' || target.tagName === 'SELECT') scheduleSettingsPreview();
    });

    _tvOverlayContainer(chartId).appendChild(overlay);
}

// ---------------------------------------------------------------------------
// Normalize a raw symbol item (from search/resolve) into a consistent shape.
// Shared by compare panel and indicator symbol picker.
// ---------------------------------------------------------------------------
function _tvNormalizeSymbolInfo(item) {
    if (!item || typeof item !== 'object') return null;
    var symbol = String(item.symbol || item.ticker || '').trim();
    if (!symbol) return null;
    var ticker = String(item.ticker || '').trim().toUpperCase();
    if (!ticker) {
        ticker = symbol.indexOf(':') >= 0 ? symbol.split(':').pop().trim().toUpperCase() : symbol.toUpperCase();
    }
    var fullName = String(item.fullName || item.full_name || '').trim();
    var description = String(item.description || '').trim();
    var exchange = String(item.exchange || item.listedExchange || item.listed_exchange || '').trim();
    var symbolType = String(item.type || item.symbolType || item.symbol_type || '').trim();
    var currency = String(item.currency || item.currencyCode || item.currency_code || '').trim();
    return {
        symbol: symbol,
        ticker: ticker,
        displaySymbol: ticker || symbol,
        requestSymbol: ticker || symbol,
        fullName: fullName,
        description: description,
        exchange: exchange,
        type: symbolType,
        currency: currency,
        pricescale: item.pricescale,
        minmov: item.minmov,
        timezone: item.timezone,
        session: item.session,
    };
}

function _tvShowComparePanel(chartId) {
    _tvHideComparePanel();
    var resolved = _tvResolveChartEntry(chartId);
    if (!resolved || !resolved.entry) return;
    chartId = resolved.chartId;
    var entry = resolved.entry;
    var ds = window.__PYWRY_DRAWINGS__[chartId] || _tvEnsureDrawingLayer(chartId);
    if (!ds) return;

    if (!entry._compareSymbols) entry._compareSymbols = {};
    if (!entry._compareLabels) entry._compareLabels = {};

    var overlay = document.createElement('div');
    overlay.className = 'tv-settings-overlay';
    _compareOverlay = overlay;
    _compareOverlayChartId = chartId;
    _tvSetChartInteractionLocked(chartId, true);
    _tvRefreshLegendVisibility();
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) _tvHideComparePanel();
    });
    overlay.addEventListener('mousedown', function(e) { e.stopPropagation(); });
    overlay.addEventListener('wheel', function(e) { e.stopPropagation(); });

    var panel = document.createElement('div');
    panel.className = 'tv-compare-panel';
    overlay.appendChild(panel);

    // Header
    var header = document.createElement('div');
    header.className = 'tv-compare-header';
    var title = document.createElement('h3');
    title.textContent = 'Compare symbol';
    header.appendChild(title);
    var closeBtn = document.createElement('button');
    closeBtn.className = 'tv-settings-close';
    closeBtn.innerHTML = '<svg viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>';
    closeBtn.addEventListener('click', function() { _tvHideComparePanel(); });
    header.appendChild(closeBtn);
    panel.appendChild(header);

    // Search row
    var searchRow = document.createElement('div');
    searchRow.className = 'tv-compare-search-row';
    var searchIcon = document.createElement('span');
    searchIcon.className = 'tv-compare-search-icon';
    searchIcon.innerHTML = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="6.5" cy="6.5" r="4"/><line x1="10" y1="10" x2="14" y2="14"/></svg>';
    searchRow.appendChild(searchIcon);
    var searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.className = 'tv-compare-search-input';
    searchInput.placeholder = 'Search';
    searchInput.autocomplete = 'off';
    searchInput.spellcheck = false;
    searchRow.appendChild(searchInput);
    var addBtn = document.createElement('button');
    addBtn.type = 'button';
    addBtn.className = 'tv-compare-add-btn';
    addBtn.innerHTML = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="3" x2="8" y2="13"/><line x1="3" y1="8" x2="13" y2="8"/></svg>';
    addBtn.title = 'Add symbol';
    searchRow.appendChild(addBtn);
    panel.appendChild(searchRow);

    // Filter row — exchange and type dropdowns from datafeed config
    var filterRow = document.createElement('div');
    filterRow.className = 'tv-symbol-search-filters';

    var exchangeSelect = document.createElement('select');
    exchangeSelect.className = 'tv-symbol-search-filter-select';
    var exchangeDefault = document.createElement('option');
    exchangeDefault.value = '';
    exchangeDefault.textContent = 'All Exchanges';
    exchangeSelect.appendChild(exchangeDefault);

    var typeSelect = document.createElement('select');
    typeSelect.className = 'tv-symbol-search-filter-select';
    var typeDefault = document.createElement('option');
    typeDefault.value = '';
    typeDefault.textContent = 'All Types';
    typeSelect.appendChild(typeDefault);

    var cfg = entry._datafeedConfig || {};
    var exchanges = cfg.exchanges || [];
    for (var ei = 0; ei < exchanges.length; ei++) {
        if (!exchanges[ei].value) continue;
        var opt = document.createElement('option');
        opt.value = exchanges[ei].value;
        opt.textContent = exchanges[ei].name || exchanges[ei].value;
        exchangeSelect.appendChild(opt);
    }
    var symTypes = cfg.symbols_types || cfg.symbolsTypes || [];
    for (var ti = 0; ti < symTypes.length; ti++) {
        if (!symTypes[ti].value) continue;
        var topt = document.createElement('option');
        topt.value = symTypes[ti].value;
        topt.textContent = symTypes[ti].name || symTypes[ti].value;
        typeSelect.appendChild(topt);
    }

    filterRow.appendChild(exchangeSelect);
    filterRow.appendChild(typeSelect);
    panel.appendChild(filterRow);

    exchangeSelect.addEventListener('change', function() {
        if ((searchInput.value || '').trim()) requestSearch(searchInput.value);
    });
    typeSelect.addEventListener('change', function() {
        if ((searchInput.value || '').trim()) requestSearch(searchInput.value);
    });

    var searchResults = [];
    var selectedResult = null;
    var pendingSearchRequestId = null;
    var searchDebounce = null;
    var searchResultLimit = Math.max(3, Math.min(20, Number(window.__PYWRY_TVCHART_COMPARE_RESULT_LIMIT__ || 6) || 6));

    var resultsArea = document.createElement('div');
    resultsArea.className = 'tv-compare-results';
    panel.appendChild(resultsArea);

    function isSearchMode() {
        return String(searchInput.value || '').trim().length > 0;
    }

    function syncCompareSectionsVisibility() {
        var searching = isSearchMode();
        resultsArea.style.display = searching ? '' : 'none';
        listArea.style.display = searching ? 'none' : '';
    }

    function _tvSymbolCaption(info) {
        var parts = [];
        if (info.exchange) parts.push(info.exchange);
        if (info.type) parts.push(info.type);
        if (info.currency) parts.push(info.currency);
        return parts.join(' · ');
    }

    function renderSearchResults() {
        resultsArea.innerHTML = '';
        resultsArea.style.overflowY = 'hidden';
        resultsArea.style.maxHeight = (searchResultLimit * 84) + 'px';
        if (!searchResults.length) {
            if (isSearchMode()) {
                var emptySearch = document.createElement('div');
                emptySearch.className = 'tv-compare-search-empty';
                emptySearch.textContent = 'No symbols found';
                resultsArea.appendChild(emptySearch);
            }
            syncCompareSectionsVisibility();
            return;
        }
        var list = document.createElement('div');
        list.className = 'tv-compare-results-list';
        for (var i = 0; i < Math.min(searchResults.length, searchResultLimit); i++) {
            (function(info) {
                var row = document.createElement('div');
                row.className = 'tv-compare-result-row';

                var identity = document.createElement('div');
                identity.className = 'tv-compare-result-identity';

                var badge = document.createElement('div');
                badge.className = 'tv-compare-result-badge';
                badge.textContent = (info.symbol || '?').slice(0, 1);
                identity.appendChild(badge);

                var copy = document.createElement('div');
                copy.className = 'tv-compare-result-copy';

                var top = document.createElement('div');
                top.className = 'tv-compare-result-top';

                var symbol = document.createElement('span');
                symbol.className = 'tv-compare-result-symbol';
                symbol.textContent = info.displaySymbol || info.symbol;
                top.appendChild(symbol);

                var caption = _tvSymbolCaption(info);
                if (caption) {
                    var meta = document.createElement('span');
                    meta.className = 'tv-compare-result-meta';
                    meta.textContent = caption;
                    top.appendChild(meta);
                }

                copy.appendChild(top);

                var detail = info.fullName || info.description;
                if (detail) {
                    var sub = document.createElement('div');
                    sub.className = 'tv-compare-result-sub';
                    sub.textContent = detail;
                    copy.appendChild(sub);
                }

                identity.appendChild(copy);
                row.appendChild(identity);

                var actions = document.createElement('div');
                actions.className = 'tv-compare-result-actions';

                function makeAction(label, mode, primary) {
                    var btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = primary
                        ? 'tv-compare-result-action tv-compare-result-action-primary'
                        : 'tv-compare-result-action';
                    btn.textContent = label;
                    btn.addEventListener('click', function(e) {
                        e.preventDefault();
                        e.stopPropagation();
                        selectedResult = info;
                        searchInput.value = info.symbol;
                        addCompare(info, mode);
                    });
                    return btn;
                }

                actions.appendChild(makeAction('Same % scale', 'same_percent', true));
                actions.appendChild(makeAction('New price scale', 'new_price_scale', false));
                actions.appendChild(makeAction('New pane', 'new_pane', false));
                row.appendChild(actions);

                row.addEventListener('click', function() {
                    selectedResult = info;
                    searchInput.value = info.symbol;
                    addCompare(info, 'same_percent');
                });

                list.appendChild(row);
            })(searchResults[i]);
        }
        resultsArea.appendChild(list);
        syncCompareSectionsVisibility();
    }

    function requestSearch(query) {
        query = String(query || '').trim();
        var normalizedQuery = query.toUpperCase();
        if (normalizedQuery.indexOf(':') >= 0) {
            normalizedQuery = normalizedQuery.split(':').pop().trim();
        }
        searchResults = [];
        selectedResult = null;
        renderSearchResults();
        if (!normalizedQuery || normalizedQuery.length < 1) return;

        var exch = exchangeSelect.value || '';
        var stype = typeSelect.value || '';

        pendingSearchRequestId = _tvRequestDatafeedSearch(chartId, normalizedQuery, searchResultLimit, function(resp) {
            if (!resp || resp.requestId !== pendingSearchRequestId) return;
            pendingSearchRequestId = null;
            if (resp.error) {
                searchResults = [];
                renderSearchResults();
                return;
            }
            var items = Array.isArray(resp.items) ? resp.items : [];
            var normalized = [];
            for (var idx = 0; idx < items.length; idx++) {
                var parsed = _tvNormalizeSymbolInfo(items[idx]);
                if (parsed) normalized.push(parsed);
            }
            searchResults = normalized;
            renderSearchResults();
        }, exch, stype);
    }

    // Symbols list area
    var listArea = document.createElement('div');
    listArea.className = 'tv-compare-list';

    function renderSymbolList() {
        listArea.innerHTML = '';
        var compareKeys = Object.keys(entry._compareSymbols || {}).filter(function(sid) {
            return !(entry._indicatorSourceSeries && entry._indicatorSourceSeries[sid]);
        });
        if (compareKeys.length === 0) {
            var empty = document.createElement('div');
            empty.className = 'tv-compare-empty';
            var emptyIcon = document.createElement('div');
            emptyIcon.className = 'tv-compare-empty-icon';
            emptyIcon.innerHTML = '<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="20" cy="20" r="12"/><line x1="30" y1="30" x2="43" y2="43"/><circle cx="39" cy="9" r="5" fill="currentColor" stroke="none" opacity="0.85"/><line x1="36" y1="9" x2="42" y2="9" stroke="white" stroke-width="2"/><line x1="39" y1="6" x2="39" y2="12" stroke="white" stroke-width="2"/></svg>';
            empty.appendChild(emptyIcon);
            var emptyText = document.createElement('div');
            emptyText.className = 'tv-compare-empty-text';
            emptyText.textContent = 'No symbols here yet \u2014 why not add some?';
            empty.appendChild(emptyText);
            listArea.appendChild(empty);
        } else {
            compareKeys.forEach(function(seriesId) {
                var symbolName = entry._compareLabels[seriesId] || _tvDisplayLabelFromSymbolInfo(
                    entry._compareSymbolInfo && entry._compareSymbolInfo[seriesId] ? entry._compareSymbolInfo[seriesId] : null,
                    entry._compareSymbols[seriesId] || seriesId
                );
                var row = document.createElement('div');
                row.className = 'tv-compare-symbol-row';

                var dot = document.createElement('span');
                dot.className = 'tv-compare-symbol-dot';
                row.appendChild(dot);

                var lbl = document.createElement('span');
                lbl.className = 'tv-compare-symbol-label';
                lbl.textContent = symbolName;
                row.appendChild(lbl);

                var rmBtn = document.createElement('button');
                rmBtn.type = 'button';
                rmBtn.className = 'tv-compare-symbol-remove';
                rmBtn.innerHTML = '<svg viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>';
                rmBtn.title = 'Remove';
                rmBtn.addEventListener('click', function() {
                    if (window.pywry) {
                        window.pywry.emit('tvchart:remove-series', { chartId: chartId, seriesId: seriesId });
                    }
                    delete entry._compareSymbols[seriesId];
                    if (entry._compareLabels && entry._compareLabels[seriesId]) {
                        delete entry._compareLabels[seriesId];
                    }
                    renderSymbolList();
                });
                row.appendChild(rmBtn);
                listArea.appendChild(row);
            });
        }
        syncCompareSectionsVisibility();
    }

    renderSymbolList();
    panel.appendChild(listArea);

    // Footer: Allow extend time scale
    var footer = document.createElement('div');
    footer.className = 'tv-compare-footer';
    var extendLabel = document.createElement('label');
    extendLabel.className = 'tv-compare-extend-label';
    var extendCheck = document.createElement('input');
    extendCheck.type = 'checkbox';
    extendCheck.className = 'tv-compare-extend-check';
    extendCheck.checked = !!(entry._chartPrefs && entry._chartPrefs.compareExtendTimeScale);
    extendCheck.addEventListener('change', function() {
        if (!entry._chartPrefs) entry._chartPrefs = {};
        entry._chartPrefs.compareExtendTimeScale = extendCheck.checked;
    });
    extendLabel.appendChild(extendCheck);
    var extendText = document.createElement('span');
    extendText.textContent = 'Allow extend time scale';
    extendLabel.appendChild(extendText);
    footer.appendChild(extendLabel);
    panel.appendChild(footer);

    function addCompare(selectedInfo, compareMode) {
        var symbol = (searchInput.value || '').trim().toUpperCase();
        if (selectedInfo && selectedInfo.requestSymbol) symbol = String(selectedInfo.requestSymbol).trim().toUpperCase();
        if (!symbol || !window.pywry) return;
        compareMode = compareMode || 'same_percent';

        function emitCompareRequest(symbolInfo) {
            var existingId = null;
            var syms = entry._compareSymbols || {};
            var symKeys = Object.keys(syms);
            for (var i = 0; i < symKeys.length; i++) {
                if (syms[symKeys[i]] === symbol) { existingId = symKeys[i]; break; }
            }
            var seriesId = existingId || ('compare-' + symbol.toLowerCase().replace(/[^a-z0-9]/g, '_'));
            entry._compareSymbols[seriesId] = symbol;
            if (!entry._compareSymbolInfo) entry._compareSymbolInfo = {};
            if (symbolInfo || selectedInfo) {
                entry._compareSymbolInfo[seriesId] = symbolInfo || selectedInfo;
            }
            if (!entry._compareLabels) entry._compareLabels = {};
            entry._compareLabels[seriesId] = _tvDisplayLabelFromSymbolInfo(symbolInfo || selectedInfo || null, symbol);
            if (!entry._pendingCompareModes) entry._pendingCompareModes = {};
            entry._pendingCompareModes[seriesId] = compareMode;
            var activeInterval = _tvCurrentInterval(chartId);
            var comparePeriodParams = _tvBuildPeriodParams(entry, seriesId);
            comparePeriodParams.firstDataRequest = _tvMarkFirstDataRequest(entry, seriesId);
            window.pywry.emit('tvchart:data-request', {
                chartId: chartId,
                symbol: symbol,
                seriesId: seriesId,
                compareMode: compareMode,
                symbolInfo: symbolInfo || selectedInfo || null,
                interval: activeInterval,
                resolution: activeInterval,
                periodParams: comparePeriodParams,
            });
            searchInput.value = '';
            searchResults = [];
            selectedResult = null;
            renderSearchResults();
            renderSymbolList();
        }

        if (selectedInfo) {
            emitCompareRequest(selectedInfo);
            return;
        }

        _tvRequestDatafeedResolve(chartId, symbol, function(resp) {
            var resolved = null;
            if (resp && resp.symbolInfo) {
                resolved = _tvNormalizeSymbolInfo(resp.symbolInfo);
            }
            emitCompareRequest(resolved);
        });
    }

    addBtn.addEventListener('click', function() {
        addCompare(selectedResult, 'same_percent');
    });

    searchInput.addEventListener('input', function() {
        var raw = searchInput.value || '';
        if (searchDebounce) clearTimeout(searchDebounce);
        searchDebounce = setTimeout(function() {
            requestSearch(raw);
        }, 180);
    });

    searchInput.addEventListener('keydown', function(e) {
        e.stopPropagation();
        if (e.key === 'Escape') {
            _tvHideComparePanel();
            return;
        }
        if (e.key === 'Enter' && (searchInput.value || '').trim()) {
            addCompare(selectedResult, 'same_percent');
        }
    });

    // Attach compare action to Enter key (already done above)
    // Make the search bar trigger add on blur if non-empty? No - wait for Enter.

    syncCompareSectionsVisibility();

    ds.uiLayer.appendChild(overlay);
    searchInput.focus();
}

// ---------------------------------------------------------------------------
// Indicator Symbol Picker – shown when a binary indicator (Spread, Ratio,
// Product, Sum, Correlation) is added but no secondary series exists yet.
// ---------------------------------------------------------------------------
var _indicatorPickerOverlay = null;
var _indicatorPickerChartId = null;

function _tvHideIndicatorSymbolPicker() {
    if (_indicatorPickerOverlay && _indicatorPickerOverlay.parentNode) {
        _indicatorPickerOverlay.parentNode.removeChild(_indicatorPickerOverlay);
    }
    if (_indicatorPickerChartId) _tvSetChartInteractionLocked(_indicatorPickerChartId, false);
    _indicatorPickerOverlay = null;
    _indicatorPickerChartId = null;
    _tvRefreshLegendVisibility();
}

function _tvShowIndicatorSymbolPicker(chartId, indicatorDef) {
    _tvHideIndicatorSymbolPicker();
    var resolved = _tvResolveChartEntry(chartId);
    if (!resolved || !resolved.entry) return;
    chartId = resolved.chartId;
    var entry = resolved.entry;
    var ds = window.__PYWRY_DRAWINGS__[chartId] || _tvEnsureDrawingLayer(chartId);
    if (!ds) return;

    var overlay = document.createElement('div');
    overlay.className = 'tv-settings-overlay';
    _indicatorPickerOverlay = overlay;
    _indicatorPickerChartId = chartId;
    _tvSetChartInteractionLocked(chartId, true);
    _tvRefreshLegendVisibility();
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) _tvHideIndicatorSymbolPicker();
    });
    overlay.addEventListener('mousedown', function(e) { e.stopPropagation(); });
    overlay.addEventListener('wheel', function(e) { e.stopPropagation(); });

    var panel = document.createElement('div');
    panel.className = 'tv-symbol-search-panel';
    overlay.appendChild(panel);

    // Header
    var header = document.createElement('div');
    header.className = 'tv-compare-header';
    var title = document.createElement('h3');
    title.textContent = 'Add Symbol \u2014 ' + (indicatorDef.fullName || indicatorDef.name);
    header.appendChild(title);
    var closeBtn = document.createElement('button');
    closeBtn.className = 'tv-settings-close';
    closeBtn.innerHTML = '<svg viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>';
    closeBtn.addEventListener('click', function() { _tvHideIndicatorSymbolPicker(); });
    header.appendChild(closeBtn);
    panel.appendChild(header);

    // Search row
    var searchRow = document.createElement('div');
    searchRow.className = 'tv-compare-search-row';
    var searchIcon = document.createElement('span');
    searchIcon.className = 'tv-compare-search-icon';
    searchIcon.innerHTML = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="6.5" cy="6.5" r="4"/><line x1="10" y1="10" x2="14" y2="14"/></svg>';
    searchRow.appendChild(searchIcon);
    var searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.className = 'tv-compare-search-input';
    searchInput.placeholder = 'Search symbol...';
    searchInput.autocomplete = 'off';
    searchInput.spellcheck = false;
    searchRow.appendChild(searchInput);
    panel.appendChild(searchRow);

    // Filter row — exchange and type dropdowns from datafeed config
    var filterRow = document.createElement('div');
    filterRow.className = 'tv-symbol-search-filters';

    var exchangeSelect = document.createElement('select');
    exchangeSelect.className = 'tv-symbol-search-filter-select';
    var exchangeDefault = document.createElement('option');
    exchangeDefault.value = '';
    exchangeDefault.textContent = 'All Exchanges';
    exchangeSelect.appendChild(exchangeDefault);

    var typeSelect = document.createElement('select');
    typeSelect.className = 'tv-symbol-search-filter-select';
    var typeDefault = document.createElement('option');
    typeDefault.value = '';
    typeDefault.textContent = 'All Types';
    typeSelect.appendChild(typeDefault);

    var cfg = entry._datafeedConfig || {};
    var exchanges = cfg.exchanges || [];
    for (var ei = 0; ei < exchanges.length; ei++) {
        if (!exchanges[ei].value) continue;
        var opt = document.createElement('option');
        opt.value = exchanges[ei].value;
        opt.textContent = exchanges[ei].name || exchanges[ei].value;
        exchangeSelect.appendChild(opt);
    }
    var symTypes = cfg.symbols_types || cfg.symbolsTypes || [];
    for (var ti = 0; ti < symTypes.length; ti++) {
        if (!symTypes[ti].value) continue;
        var topt = document.createElement('option');
        topt.value = symTypes[ti].value;
        topt.textContent = symTypes[ti].name || symTypes[ti].value;
        typeSelect.appendChild(topt);
    }

    filterRow.appendChild(exchangeSelect);
    filterRow.appendChild(typeSelect);
    panel.appendChild(filterRow);

    exchangeSelect.addEventListener('change', function() {
        if ((searchInput.value || '').trim()) requestSearch(searchInput.value);
    });
    typeSelect.addEventListener('change', function() {
        if ((searchInput.value || '').trim()) requestSearch(searchInput.value);
    });

    var searchResults = [];
    var pendingSearchRequestId = null;
    var searchDebounce = null;
    var maxResults = 50;

    var resultsArea = document.createElement('div');
    resultsArea.className = 'tv-symbol-search-results';
    panel.appendChild(resultsArea);

    function renderSearchResults() {
        resultsArea.innerHTML = '';
        if (!searchResults.length) {
            if ((searchInput.value || '').trim().length > 0) {
                var emptyMsg = document.createElement('div');
                emptyMsg.className = 'tv-compare-search-empty';
                emptyMsg.textContent = 'No symbols found';
                resultsArea.appendChild(emptyMsg);
            }
            return;
        }
        var list = document.createElement('div');
        list.className = 'tv-compare-results-list';
        for (var i = 0; i < searchResults.length; i++) {
            (function(info) {
                var row = document.createElement('div');
                row.className = 'tv-compare-result-row tv-symbol-search-result-row';
                row.style.cursor = 'pointer';

                var identity = document.createElement('div');
                identity.className = 'tv-compare-result-identity';

                var badge = document.createElement('div');
                badge.className = 'tv-compare-result-badge';
                badge.textContent = (info.symbol || '?').slice(0, 1);
                identity.appendChild(badge);

                var copy = document.createElement('div');
                copy.className = 'tv-compare-result-copy';
                var top = document.createElement('div');
                top.className = 'tv-compare-result-top';
                var symbol = document.createElement('span');
                symbol.className = 'tv-compare-result-symbol';
                symbol.textContent = info.displaySymbol || info.symbol;
                top.appendChild(symbol);

                // Right-side meta: exchange · type
                var parts = [];
                if (info.exchange) parts.push(info.exchange);
                if (info.type) parts.push(info.type);
                if (parts.length) {
                    var meta = document.createElement('span');
                    meta.className = 'tv-compare-result-meta';
                    meta.textContent = parts.join(' \u00b7 ');
                    top.appendChild(meta);
                }
                copy.appendChild(top);

                // Subtitle: actual security name
                var nameText = info.fullName || info.description;
                if (nameText) {
                    var sub = document.createElement('div');
                    sub.className = 'tv-compare-result-sub';
                    sub.textContent = nameText;
                    copy.appendChild(sub);
                }
                identity.appendChild(copy);
                row.appendChild(identity);

                row.addEventListener('click', function() {
                    pickSymbol(info);
                });
                list.appendChild(row);
            })(searchResults[i]);
        }
        resultsArea.appendChild(list);
    }

    function requestSearch(query) {
        query = String(query || '').trim();
        var normalizedQuery = query.toUpperCase();
        if (normalizedQuery.indexOf(':') >= 0) {
            normalizedQuery = normalizedQuery.split(':').pop().trim();
        }
        searchResults = [];
        renderSearchResults();
        if (!normalizedQuery || normalizedQuery.length < 1) return;

        var exch = exchangeSelect.value || '';
        var stype = typeSelect.value || '';

        pendingSearchRequestId = _tvRequestDatafeedSearch(chartId, normalizedQuery, maxResults, function(resp) {
            if (!resp || resp.requestId !== pendingSearchRequestId) return;
            pendingSearchRequestId = null;
            if (resp.error) { searchResults = []; renderSearchResults(); return; }
            var items = Array.isArray(resp.items) ? resp.items : [];
            var normalized = [];
            for (var idx = 0; idx < items.length; idx++) {
                var parsed = _tvNormalizeSymbolInfo(items[idx]);
                if (parsed) normalized.push(parsed);
            }
            searchResults = normalized;
            renderSearchResults();
        }, exch, stype);
    }

    function pickSymbol(selectedInfo) {
        var sym = selectedInfo && selectedInfo.requestSymbol
            ? String(selectedInfo.requestSymbol).trim().toUpperCase()
            : (searchInput.value || '').trim().toUpperCase();
        if (!sym || !window.pywry) return;

        // Store the pending binary indicator so the data-response handler
        // can trigger _tvAddIndicator once the secondary data arrives.
        entry._pendingBinaryIndicator = indicatorDef;

        var seriesId = 'compare-' + sym.toLowerCase().replace(/[^a-z0-9]/g, '_');

        // Track that this compare series is an indicator source (not user-visible compare)
        if (!entry._indicatorSourceSeries) entry._indicatorSourceSeries = {};
        entry._indicatorSourceSeries[seriesId] = true;

        if (!entry._compareSymbols) entry._compareSymbols = {};
        entry._compareSymbols[seriesId] = sym;
        if (!entry._compareSymbolInfo) entry._compareSymbolInfo = {};
        if (selectedInfo) entry._compareSymbolInfo[seriesId] = selectedInfo;
        if (!entry._compareLabels) entry._compareLabels = {};
        entry._compareLabels[seriesId] = _tvDisplayLabelFromSymbolInfo(selectedInfo || null, sym);
        if (!entry._pendingCompareModes) entry._pendingCompareModes = {};
        entry._pendingCompareModes[seriesId] = 'new_price_scale';

        var activeInterval = _tvCurrentInterval(chartId);
        var comparePeriodParams = _tvBuildPeriodParams(entry, seriesId);
        comparePeriodParams.firstDataRequest = _tvMarkFirstDataRequest(entry, seriesId);

        window.pywry.emit('tvchart:data-request', {
            chartId: chartId,
            symbol: sym,
            seriesId: seriesId,
            compareMode: 'new_price_scale',
            symbolInfo: selectedInfo || null,
            interval: activeInterval,
            resolution: activeInterval,
            periodParams: comparePeriodParams,
            _forIndicator: true,
        });

        _tvHideIndicatorSymbolPicker();
    }

    searchInput.addEventListener('input', function() {
        var raw = searchInput.value || '';
        if (searchDebounce) clearTimeout(searchDebounce);
        searchDebounce = setTimeout(function() { requestSearch(raw); }, 180);
    });

    searchInput.addEventListener('keydown', function(e) {
        e.stopPropagation();
        if (e.key === 'Escape') {
            _tvHideIndicatorSymbolPicker();
            return;
        }
        if (e.key === 'Enter' && (searchInput.value || '').trim()) {
            if (searchResults.length > 0) {
                pickSymbol(searchResults[0]);
            } else {
                // Resolve the typed symbol directly
                var sym = (searchInput.value || '').trim().toUpperCase();
                _tvRequestDatafeedResolve(chartId, sym, function(resp) {
                    var resolved = null;
                    if (resp && resp.symbolInfo) resolved = _tvNormalizeSymbolInfo(resp.symbolInfo);
                    pickSymbol(resolved || { symbol: sym, ticker: sym, displaySymbol: sym, requestSymbol: sym });
                });
            }
        }
    });

    ds.uiLayer.appendChild(overlay);
    searchInput.focus();
}

function _tvShowDrawingSettings(chartId, drawIdx) {
    _tvHideDrawingSettings();
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds || drawIdx < 0 || drawIdx >= ds.drawings.length) return;
    var d = ds.drawings[drawIdx];
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry) return;

    // Clone properties for cancel support
    var draft = Object.assign({}, d);

    var overlay = document.createElement('div');
    overlay.className = 'tv-settings-overlay';
    _settingsOverlay = overlay;
    _settingsOverlayChartId = chartId;
    _tvSetChartInteractionLocked(chartId, true);
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) _tvHideDrawingSettings();
    });
    overlay.addEventListener('mousedown', function(e) { e.stopPropagation(); });
    overlay.addEventListener('wheel', function(e) { e.stopPropagation(); });

    var panel = document.createElement('div');
    panel.className = 'tv-settings-panel';
    panel.style.flexDirection = 'column';
    panel.style.width = '560px';
    overlay.appendChild(panel);

    // Header
    var header = document.createElement('div');
    header.className = 'tv-settings-header';
    header.style.cssText = 'position:relative;flex-direction:column;align-items:stretch;padding-bottom:0;';
    var hdrRow = document.createElement('div');
    hdrRow.style.cssText = 'display:flex;align-items:center;gap:8px;';
    var title = document.createElement('h3');
    title.textContent = _DRAW_TYPE_NAMES[d.type] || d.type;
    hdrRow.appendChild(title);
    var closeBtn = document.createElement('button');
    closeBtn.className = 'tv-settings-close';
    closeBtn.innerHTML = '<svg viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>';
    closeBtn.addEventListener('click', function() { _tvHideDrawingSettings(); });
    hdrRow.appendChild(closeBtn);
    header.appendChild(hdrRow);

    // Tabs — Text tab for text drawing type and line tools
    // Build tab list per drawing type (matching TradingView layout)
    var tabs = [];
    var _inputsTools = ['regression_channel', 'fibonacci', 'trendline',
        'fib_extension', 'fib_channel', 'fib_timezone', 'fib_fan',
        'fib_arc', 'fib_circle', 'fib_wedge', 'pitchfan',
        'fib_time', 'gann_box', 'gann_square_fixed', 'gann_square', 'gann_fan',
        'long_position', 'short_position', 'forecast'];
    if (_inputsTools.indexOf(d.type) !== -1) tabs.push('Inputs');
    tabs.push('Style');
    var _textTabTools = ['text', 'trendline', 'ray', 'extended_line', 'arrow_marker', 'arrow', 'arrow_mark_up', 'arrow_mark_down', 'arrow_mark_left', 'arrow_mark_right', 'anchored_text', 'note', 'price_note', 'pin', 'callout', 'comment', 'price_label', 'signpost', 'flag_mark'];
    if (_textTabTools.indexOf(d.type) !== -1) tabs.push('Text');
    tabs.push('Coordinates', 'Visibility');
    var activeTab = tabs[0];

    var tabBar = document.createElement('div');
    tabBar.className = 'tv-settings-tabs';
    header.appendChild(tabBar);
    panel.appendChild(header);

    var body = document.createElement('div');
    body.className = 'tv-settings-body';
    body.style.cssText = 'flex:1;overflow-y:auto;';
    panel.appendChild(body);

    function renderTabs() {
        tabBar.innerHTML = '';
        for (var ti = 0; ti < tabs.length; ti++) {
            (function(tname) {
                var tab = document.createElement('div');
                tab.className = 'tv-settings-tab' + (tname === activeTab ? ' active' : '');
                tab.textContent = tname;
                tab.addEventListener('click', function() {
                    activeTab = tname;
                    renderTabs();
                    renderBody();
                });
                tabBar.appendChild(tab);
            })(tabs[ti]);
        }
    }

    function makeRow(labelText) {
        var row = document.createElement('div');
        row.className = 'tv-settings-row';
        var lbl = document.createElement('label');
        lbl.textContent = labelText;
        row.appendChild(lbl);
        var ctrl = document.createElement('div');
        ctrl.className = 'ts-controls';
        row.appendChild(ctrl);
        return { row: row, ctrl: ctrl };
    }

    function makeColorSwatch(color, onChange) {
        var sw = document.createElement('div');
        sw.className = 'ts-swatch';
        sw.dataset.baseColor = _tvColorToHex(color || '#aeb4c2', '#aeb4c2');
        sw.dataset.opacity = String(_tvColorOpacityPercent(color, 100));
        sw.style.background = color;
        sw.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            _tvShowColorOpacityPopup(
                sw,
                sw.dataset.baseColor || color,
                _tvToNumber(sw.dataset.opacity, 100),
                overlay,
                function(newColor, newOpacity) {
                    sw.dataset.baseColor = newColor;
                    sw.dataset.opacity = String(newOpacity);
                    sw.style.background = _tvColorWithOpacity(newColor, newOpacity, newColor);
                    color = newColor;
                    onChange(_tvColorWithOpacity(newColor, newOpacity, newColor), newOpacity);
                }
            );
        });
        return sw;
    }

    function makeSelect(options, current, onChange) {
        var sel = document.createElement('select');
        sel.className = 'ts-select';
        for (var si = 0; si < options.length; si++) {
            var opt = document.createElement('option');
            opt.value = options[si].value !== undefined ? options[si].value : options[si];
            opt.textContent = options[si].label || options[si];
            if (String(opt.value) === String(current)) opt.selected = true;
            sel.appendChild(opt);
        }
        sel.addEventListener('change', function() { onChange(sel.value); });
        return sel;
    }

    function makeCheckbox(checked, onChange) {
        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'ts-checkbox';
        cb.checked = !!checked;
        cb.addEventListener('change', function() { onChange(cb.checked); });
        return cb;
    }

    function makeTextInput(val, onChange) {
        var inp = document.createElement('input');
        inp.type = 'text';
        inp.className = 'ts-input ts-input-full';
        inp.value = val || '';
        inp.addEventListener('input', function() { onChange(inp.value); });
        inp.addEventListener('keydown', function(e) { e.stopPropagation(); });
        return inp;
    }

    function makeNumberInput(val, onChange) {
        var inp = document.createElement('input');
        inp.type = 'number';
        inp.className = 'ts-input';
        inp.value = val;
        inp.step = 'any';
        inp.addEventListener('input', function() { onChange(parseFloat(inp.value)); });
        inp.addEventListener('keydown', function(e) { e.stopPropagation(); });
        return inp;
    }

    function makeOpacityInput(val, onChange) {
        var wrap = document.createElement('div');
        wrap.style.cssText = 'display:flex;align-items:center;gap:6px;';
        var slider = document.createElement('input');
        slider.type = 'range';
        slider.className = 'tv-settings-slider';
        slider.min = '0'; slider.max = '100';
        slider.value = String(Math.round((val !== undefined ? val : 0.15) * 100));
        var numBox = document.createElement('input');
        numBox.type = 'number';
        numBox.className = 'ts-input ts-input-sm';
        numBox.min = '0'; numBox.max = '100';
        numBox.value = slider.value;
        numBox.addEventListener('keydown', function(e) { e.stopPropagation(); });
        slider.addEventListener('input', function() {
            numBox.value = slider.value;
            onChange(parseInt(slider.value) / 100);
        });
        numBox.addEventListener('input', function() {
            slider.value = numBox.value;
            onChange(parseInt(numBox.value) / 100);
        });
        var pct = document.createElement('span');
        pct.className = 'tv-settings-unit';
        pct.textContent = '%';
        wrap.appendChild(slider); wrap.appendChild(numBox); wrap.appendChild(pct);
        return wrap;
    }

    function addSectionHeading(text) {
        var sec = document.createElement('div');
        sec.className = 'tv-settings-section';
        sec.textContent = text;
        body.appendChild(sec);
    }

    // Shared: Line row with color swatch + style toggle buttons
    function addLineRow(container) {
        var cRow = makeRow('Line');
        var lineSwatch = makeColorSwatch(draft.color || _drawDefaults.color, function(c) { draft.color = c; });
        cRow.ctrl.appendChild(lineSwatch);
        var styleGroup = document.createElement('div');
        styleGroup.className = 'ts-line-style-group';
        var styleOpts = [
            { val: 0, svg: '<svg width="28" height="14"><line x1="2" y1="7" x2="26" y2="7" stroke="currentColor" stroke-width="2"/></svg>' },
            { val: 1, svg: '<svg width="28" height="14"><line x1="2" y1="7" x2="26" y2="7" stroke="currentColor" stroke-width="2" stroke-dasharray="6,3"/></svg>' },
            { val: 2, svg: '<svg width="28" height="14"><line x1="2" y1="7" x2="26" y2="7" stroke="currentColor" stroke-width="2" stroke-dasharray="2,3"/></svg>' },
        ];
        var styleBtns = [];
        styleOpts.forEach(function(so) {
            var btn = document.createElement('button');
            btn.className = 'ts-line-style-btn' + (parseInt(draft.lineStyle || 0) === so.val ? ' active' : '');
            btn.innerHTML = so.svg;
            btn.addEventListener('click', function() {
                draft.lineStyle = so.val;
                styleBtns.forEach(function(b) { b.classList.remove('active'); });
                btn.classList.add('active');
            });
            styleBtns.push(btn);
            styleGroup.appendChild(btn);
        });
        cRow.ctrl.appendChild(styleGroup);
        container.appendChild(cRow.row);
    }

    // Shared: Width row
    function addWidthRow(container) {
        var wRow = makeRow('Width');
        wRow.ctrl.appendChild(makeSelect([{value:1,label:'1px'},{value:2,label:'2px'},{value:3,label:'3px'},{value:4,label:'4px'},{value:5,label:'5px'}], draft.lineWidth || 2, function(v) { draft.lineWidth = parseInt(v); }));
        container.appendChild(wRow.row);
    }

    // Shared: TV-style compound line control (checkbox + color + line-style buttons)
    // opts: { label, showKey, colorKey, styleKey, widthKey, defaultColor, defaultStyle, defaultShow }
    function addCompoundLineRow(container, opts) {
        var row = makeRow(opts.label);
        // Checkbox
        row.ctrl.appendChild(makeCheckbox(draft[opts.showKey] !== false, function(v) { draft[opts.showKey] = v; }));
        // Color swatch
        row.ctrl.appendChild(makeColorSwatch(draft[opts.colorKey] || opts.defaultColor || draft.color || _drawDefaults.color, function(c) { draft[opts.colorKey] = c; }));
        // Line style selector
        var styleGroup = document.createElement('div');
        styleGroup.className = 'ts-line-style-group';
        var styleOpts = [
            { val: 0, svg: '<svg width="28" height="14"><line x1="2" y1="7" x2="26" y2="7" stroke="currentColor" stroke-width="2"/></svg>' },
            { val: 1, svg: '<svg width="28" height="14"><line x1="2" y1="7" x2="26" y2="7" stroke="currentColor" stroke-width="2" stroke-dasharray="6,3"/></svg>' },
            { val: 2, svg: '<svg width="28" height="14"><line x1="2" y1="7" x2="26" y2="7" stroke="currentColor" stroke-width="2" stroke-dasharray="2,3"/></svg>' },
        ];
        var curStyle = draft[opts.styleKey] !== undefined ? draft[opts.styleKey] : (opts.defaultStyle || 0);
        var styleBtns = [];
        styleOpts.forEach(function(so) {
            var btn = document.createElement('button');
            btn.className = 'ts-line-style-btn' + (parseInt(curStyle) === so.val ? ' active' : '');
            btn.innerHTML = so.svg;
            btn.addEventListener('click', function() {
                draft[opts.styleKey] = so.val;
                styleBtns.forEach(function(b) { b.classList.remove('active'); });
                btn.classList.add('active');
            });
            styleBtns.push(btn);
            styleGroup.appendChild(btn);
        });
        row.ctrl.appendChild(styleGroup);
        container.appendChild(row.row);
    }

    // Shared: TV-style visibility time interval section
    function addVisibilityIntervals(container) {
        var intervals = [
            { key: 'seconds', label: 'Seconds', defFrom: 1, defTo: 59 },
            { key: 'minutes', label: 'Minutes', defFrom: 1, defTo: 59 },
            { key: 'hours', label: 'Hours', defFrom: 1, defTo: 24 },
            { key: 'days', label: 'Days', defFrom: 1, defTo: 365 },
            { key: 'weeks', label: 'Weeks', defFrom: 1, defTo: 52 },
            { key: 'months', label: 'Months', defFrom: 1, defTo: 12 },
        ];
        if (!draft.visibility) draft.visibility = {};
        for (var vi = 0; vi < intervals.length; vi++) {
            (function(itv) {
                if (!draft.visibility[itv.key]) {
                    draft.visibility[itv.key] = { enabled: true, from: itv.defFrom, to: itv.defTo };
                }
                var vis = draft.visibility[itv.key];
                var row = makeRow(itv.label);
                // Checkbox
                row.ctrl.appendChild(makeCheckbox(vis.enabled !== false, function(v) { vis.enabled = v; }));
                // From
                var fromInp = document.createElement('input');
                fromInp.type = 'number'; fromInp.className = 'ts-input ts-input-sm';
                fromInp.min = String(itv.defFrom); fromInp.max = String(itv.defTo);
                fromInp.value = String(vis.from || itv.defFrom);
                fromInp.addEventListener('input', function() { vis.from = parseInt(fromInp.value) || itv.defFrom; slider.value = String(vis.from); });
                fromInp.addEventListener('keydown', function(e) { e.stopPropagation(); });
                row.ctrl.appendChild(fromInp);
                // Slider
                var slider = document.createElement('input');
                slider.type = 'range'; slider.className = 'tv-settings-slider';
                slider.min = String(itv.defFrom); slider.max = String(itv.defTo);
                slider.value = String(vis.from || itv.defFrom);
                slider.addEventListener('input', function() { vis.from = parseInt(slider.value); fromInp.value = slider.value; });
                row.ctrl.appendChild(slider);
                // To
                var toInp = document.createElement('input');
                toInp.type = 'number'; toInp.className = 'ts-input ts-input-sm';
                toInp.min = String(itv.defFrom); toInp.max = String(itv.defTo);
                toInp.value = String(vis.to || itv.defTo);
                toInp.addEventListener('input', function() { vis.to = parseInt(toInp.value) || itv.defTo; });
                toInp.addEventListener('keydown', function(e) { e.stopPropagation(); });
                row.ctrl.appendChild(toInp);
                container.appendChild(row.row);
            })(intervals[vi]);
        }
    }

    function renderBody() {
        body.innerHTML = '';

        if (activeTab === 'Inputs') {
            // ---- INPUTS TAB ----
            if (d.type === 'regression_channel') {
                addSectionHeading('DEVIATION');
                var udRow = makeRow('Upper deviation');
                udRow.ctrl.appendChild(makeNumberInput(draft.upperDeviation !== undefined ? draft.upperDeviation : 2.0, function(v) { draft.upperDeviation = v; }));
                body.appendChild(udRow.row);
                var ldRow = makeRow('Lower deviation');
                ldRow.ctrl.appendChild(makeNumberInput(draft.lowerDeviation !== undefined ? draft.lowerDeviation : 2.0, function(v) { draft.lowerDeviation = v; }));
                body.appendChild(ldRow.row);
                var uuRow = makeRow('Use upper deviation');
                uuRow.ctrl.appendChild(makeCheckbox(draft.useUpperDeviation !== false, function(v) { draft.useUpperDeviation = v; }));
                body.appendChild(uuRow.row);
                var ulRow = makeRow('Use lower deviation');
                ulRow.ctrl.appendChild(makeCheckbox(draft.useLowerDeviation !== false, function(v) { draft.useLowerDeviation = v; }));
                body.appendChild(ulRow.row);
                addSectionHeading('SOURCE');
                var srcRow = makeRow('Source');
                srcRow.ctrl.appendChild(makeSelect([
                    {value:'close',label:'Close'},{value:'open',label:'Open'},
                    {value:'high',label:'High'},{value:'low',label:'Low'},
                    {value:'hl2',label:'(H+L)/2'},{value:'hlc3',label:'(H+L+C)/3'},
                    {value:'ohlc4',label:'(O+H+L+C)/4'}
                ], draft.source || 'close', function(v) { draft.source = v; }));
                body.appendChild(srcRow.row);

            } else if (d.type === 'fibonacci') {
                addSectionHeading('LEVELS');
                var revRow = makeRow('Reverse');
                revRow.ctrl.appendChild(makeCheckbox(!!draft.reverse, function(v) { draft.reverse = v; }));
                body.appendChild(revRow.row);
                var showLabRow = makeRow('Show labels');
                showLabRow.ctrl.appendChild(makeCheckbox(draft.showLabels !== false, function(v) { draft.showLabels = v; }));
                body.appendChild(showLabRow.row);
                var showPrRow = makeRow('Show prices');
                showPrRow.ctrl.appendChild(makeCheckbox(draft.showPrices !== false, function(v) { draft.showPrices = v; }));
                body.appendChild(showPrRow.row);
                var showLevRow = makeRow('Levels based on');
                showLevRow.ctrl.appendChild(makeSelect([
                    {value:'percent',label:'Percent'},{value:'price',label:'Price'}
                ], draft.levelsBasis || 'percent', function(v) { draft.levelsBasis = v; }));
                body.appendChild(showLevRow.row);

            } else if (d.type === 'fib_extension') {
                addSectionHeading('LEVELS');
                var revRow = makeRow('Reverse');
                revRow.ctrl.appendChild(makeCheckbox(!!draft.reverse, function(v) { draft.reverse = v; }));
                body.appendChild(revRow.row);
                var showLabRow = makeRow('Show labels');
                showLabRow.ctrl.appendChild(makeCheckbox(draft.showLabels !== false, function(v) { draft.showLabels = v; }));
                body.appendChild(showLabRow.row);
                var showPrRow = makeRow('Show prices');
                showPrRow.ctrl.appendChild(makeCheckbox(draft.showPrices !== false, function(v) { draft.showPrices = v; }));
                body.appendChild(showPrRow.row);
                var showLevRow = makeRow('Levels based on');
                showLevRow.ctrl.appendChild(makeSelect([
                    {value:'percent',label:'Percent'},{value:'price',label:'Price'}
                ], draft.levelsBasis || 'percent', function(v) { draft.levelsBasis = v; }));
                body.appendChild(showLevRow.row);

            } else if (d.type === 'fib_channel' || d.type === 'fib_fan' || d.type === 'fib_arc' ||
                       d.type === 'fib_circle' || d.type === 'fib_wedge') {
                addSectionHeading('LEVELS');
                var revRow = makeRow('Reverse');
                revRow.ctrl.appendChild(makeCheckbox(!!draft.reverse, function(v) { draft.reverse = v; }));
                body.appendChild(revRow.row);
                var showLabRow = makeRow('Show labels');
                showLabRow.ctrl.appendChild(makeCheckbox(draft.showLabels !== false, function(v) { draft.showLabels = v; }));
                body.appendChild(showLabRow.row);
                var showPrRow = makeRow('Show prices');
                showPrRow.ctrl.appendChild(makeCheckbox(draft.showPrices !== false, function(v) { draft.showPrices = v; }));
                body.appendChild(showPrRow.row);

            } else if (d.type === 'pitchfan') {
                addSectionHeading('OPTIONS');
                var showLabRow = makeRow('Show labels');
                showLabRow.ctrl.appendChild(makeCheckbox(draft.showLabels !== false, function(v) { draft.showLabels = v; }));
                body.appendChild(showLabRow.row);
                var showPrRow = makeRow('Show prices');
                showPrRow.ctrl.appendChild(makeCheckbox(draft.showPrices !== false, function(v) { draft.showPrices = v; }));
                body.appendChild(showPrRow.row);

            } else if (d.type === 'fib_timezone') {
                addSectionHeading('OPTIONS');
                var showLabRow = makeRow('Show labels');
                showLabRow.ctrl.appendChild(makeCheckbox(draft.showLabels !== false, function(v) { draft.showLabels = v; }));
                body.appendChild(showLabRow.row);

            } else if (d.type === 'fib_time') {
                addSectionHeading('OPTIONS');
                var showLabRow = makeRow('Show labels');
                showLabRow.ctrl.appendChild(makeCheckbox(draft.showLabels !== false, function(v) { draft.showLabels = v; }));
                body.appendChild(showLabRow.row);
                var revRow = makeRow('Reverse');
                revRow.ctrl.appendChild(makeCheckbox(!!draft.reverse, function(v) { draft.reverse = v; }));
                body.appendChild(revRow.row);

            } else if (d.type === 'gann_box' || d.type === 'gann_square_fixed' || d.type === 'gann_square') {
                addSectionHeading('OPTIONS');
                var revRow = makeRow('Reverse');
                revRow.ctrl.appendChild(makeCheckbox(!!draft.reverse, function(v) { draft.reverse = v; }));
                body.appendChild(revRow.row);
                var showLabRow = makeRow('Show labels');
                showLabRow.ctrl.appendChild(makeCheckbox(draft.showLabels !== false, function(v) { draft.showLabels = v; }));
                body.appendChild(showLabRow.row);

            } else if (d.type === 'gann_fan') {
                addSectionHeading('OPTIONS');
                var showLabRow = makeRow('Show labels');
                showLabRow.ctrl.appendChild(makeCheckbox(draft.showLabels !== false, function(v) { draft.showLabels = v; }));
                body.appendChild(showLabRow.row);

            } else if (d.type === 'trendline') {
                addSectionHeading('OPTIONS');
                var extRow = makeRow('Extend');
                extRow.ctrl.appendChild(makeSelect(["Don't extend", 'Left', 'Right', 'Both'], draft.extend || "Don't extend", function(v) { draft.extend = v; }));
                body.appendChild(extRow.row);
                var mpRow = makeRow('Middle point');
                mpRow.ctrl.appendChild(makeCheckbox(!!draft.showMiddlePoint, function(v) { draft.showMiddlePoint = v; }));
                body.appendChild(mpRow.row);
                var plRow = makeRow('Price labels');
                plRow.ctrl.appendChild(makeCheckbox(!!draft.showPriceLabels, function(v) { draft.showPriceLabels = v; }));
                body.appendChild(plRow.row);
                addSectionHeading('STATS');
                var statsRow = makeRow('Stats');
                statsRow.ctrl.appendChild(makeSelect([{value:'hidden',label:'Hidden'},{value:'compact',label:'Compact'},{value:'values',label:'Values'}], draft.stats || 'hidden', function(v) { draft.stats = v; }));
                body.appendChild(statsRow.row);
                var spRow = makeRow('Stats position');
                spRow.ctrl.appendChild(makeSelect([{value:'left',label:'Left'},{value:'right',label:'Right'}], draft.statsPosition || 'right', function(v) { draft.statsPosition = v; }));
                body.appendChild(spRow.row);
                var asRow = makeRow('Always show stats');
                asRow.ctrl.appendChild(makeCheckbox(!!draft.alwaysShowStats, function(v) { draft.alwaysShowStats = v; }));
                body.appendChild(asRow.row);

            } else if (d.type === 'long_position' || d.type === 'short_position') {
                addSectionHeading('RISK/REWARD');
                var rrRow = makeRow('Risk/Reward ratio');
                rrRow.ctrl.appendChild(makeNumberInput(draft.riskReward !== undefined ? draft.riskReward : 2.0, function(v) { draft.riskReward = v; }));
                body.appendChild(rrRow.row);
                var lotRow = makeRow('Lot size');
                lotRow.ctrl.appendChild(makeNumberInput(draft.lotSize !== undefined ? draft.lotSize : 1, function(v) { draft.lotSize = v; }));
                body.appendChild(lotRow.row);
                var accRow = makeRow('Account size');
                accRow.ctrl.appendChild(makeNumberInput(draft.accountSize !== undefined ? draft.accountSize : 10000, function(v) { draft.accountSize = v; }));
                body.appendChild(accRow.row);
                var showLblRow = makeRow('Show labels');
                showLblRow.ctrl.appendChild(makeCheckbox(draft.showLabels !== false, function(v) { draft.showLabels = v; }));
                body.appendChild(showLblRow.row);

            } else if (d.type === 'forecast') {
                addSectionHeading('OPTIONS');
                var srcRow = makeRow('Source');
                srcRow.ctrl.appendChild(makeSelect([
                    {value:'close',label:'Close'},{value:'open',label:'Open'},
                    {value:'high',label:'High'},{value:'low',label:'Low'}
                ], draft.source || 'close', function(v) { draft.source = v; }));
                body.appendChild(srcRow.row);
            }

        } else if (activeTab === 'Style') {

            // ---- HLINE ----
            if (d.type === 'hline') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);
                var extRow = makeRow('Extend');
                extRow.ctrl.appendChild(makeSelect(["Don't extend", 'Left', 'Right', 'Both'], draft.extend || "Don't extend", function(v) { draft.extend = v; }));
                body.appendChild(extRow.row);
                addSectionHeading('PRICE LABEL');
                var plRow = makeRow('Price label');
                plRow.ctrl.appendChild(makeCheckbox(draft.showPriceLabel !== false, function(v) { draft.showPriceLabel = v; }));
                body.appendChild(plRow.row);
                var plColorRow = makeRow('Label color');
                plColorRow.ctrl.appendChild(makeColorSwatch(draft.labelColor || draft.color || _drawDefaults.color, function(c) { draft.labelColor = c; }));
                body.appendChild(plColorRow.row);
                var plTitleRow = makeRow('Label text');
                plTitleRow.ctrl.appendChild(makeTextInput(draft.title || '', function(v) { draft.title = v; }));
                body.appendChild(plTitleRow.row);

            // ---- TRENDLINE / RAY / EXTENDED_LINE ----
            } else if (d.type === 'trendline' || d.type === 'ray' || d.type === 'extended_line') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);

            // ---- HRAY ----
            } else if (d.type === 'hray') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('PRICE LABEL');
                var plRow = makeRow('Price label');
                plRow.ctrl.appendChild(makeCheckbox(draft.showPriceLabel !== false, function(v) { draft.showPriceLabel = v; }));
                body.appendChild(plRow.row);

            // ---- VLINE ----
            } else if (d.type === 'vline') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);

            // ---- CROSSLINE ----
            } else if (d.type === 'crossline') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);

            // ---- RECT ----
            } else if (d.type === 'rect') {
                addSectionHeading('BORDER');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('BACKGROUND');
                var bgEnRow = makeRow('Background');
                bgEnRow.ctrl.appendChild(makeCheckbox(draft.fillEnabled !== false, function(v) { draft.fillEnabled = v; }));
                bgEnRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(bgEnRow.row);
                var bgOpRow = makeRow('Opacity');
                bgOpRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.15, function(v) { draft.fillOpacity = v; }));
                body.appendChild(bgOpRow.row);

            // ---- CHANNEL ----
            } else if (d.type === 'channel') {
                addSectionHeading('LINES');
                addLineRow(body);
                addWidthRow(body);
                var midRow = makeRow('Middle line');
                midRow.ctrl.appendChild(makeCheckbox(draft.showMiddleLine !== false, function(v) { draft.showMiddleLine = v; }));
                body.appendChild(midRow.row);
                var extRow = makeRow('Extend');
                extRow.ctrl.appendChild(makeSelect(["Don't extend", 'Left', 'Right', 'Both'], draft.extend || "Don't extend", function(v) { draft.extend = v; }));
                body.appendChild(extRow.row);
                addSectionHeading('BACKGROUND');
                var bgEnRow = makeRow('Background');
                bgEnRow.ctrl.appendChild(makeCheckbox(draft.fillEnabled !== false, function(v) { draft.fillEnabled = v; }));
                bgEnRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(bgEnRow.row);
                var bgOpRow = makeRow('Opacity');
                bgOpRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.08, function(v) { draft.fillOpacity = v; }));
                body.appendChild(bgOpRow.row);

            // ---- REGRESSION_CHANNEL (TV-style: Base/Up/Down lines) ----
            } else if (d.type === 'regression_channel') {
                addCompoundLineRow(body, {
                    label: 'Base', showKey: 'showBaseLine', colorKey: 'baseColor',
                    styleKey: 'baseLineStyle', defaultColor: draft.color || _drawDefaults.color, defaultStyle: 0
                });
                addCompoundLineRow(body, {
                    label: 'Up', showKey: 'showUpLine', colorKey: 'upColor',
                    styleKey: 'upLineStyle', defaultColor: draft.upColor || '#26a69a', defaultStyle: 1
                });
                addCompoundLineRow(body, {
                    label: 'Down', showKey: 'showDownLine', colorKey: 'downColor',
                    styleKey: 'downLineStyle', defaultColor: draft.downColor || '#ef5350', defaultStyle: 1
                });
                var extLnRow = makeRow('Extend lines');
                extLnRow.ctrl.appendChild(makeCheckbox(!!draft.extendLines, function(v) { draft.extendLines = v; }));
                body.appendChild(extLnRow.row);
                var prRow = makeRow("Pearson's R");
                prRow.ctrl.appendChild(makeCheckbox(!!draft.showPearsonsR, function(v) { draft.showPearsonsR = v; }));
                body.appendChild(prRow.row);
                addSectionHeading('BACKGROUND');
                var bgEnRow = makeRow('Background');
                bgEnRow.ctrl.appendChild(makeCheckbox(draft.fillEnabled !== false, function(v) { draft.fillEnabled = v; }));
                bgEnRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(bgEnRow.row);
                var bgOpRow = makeRow('Opacity');
                bgOpRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.05, function(v) { draft.fillOpacity = v; }));
                body.appendChild(bgOpRow.row);

            // ---- FLAT_CHANNEL ----
            } else if (d.type === 'flat_channel') {
                addSectionHeading('LINES');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('BACKGROUND');
                var bgEnRow = makeRow('Background');
                bgEnRow.ctrl.appendChild(makeCheckbox(draft.fillEnabled !== false, function(v) { draft.fillEnabled = v; }));
                bgEnRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(bgEnRow.row);
                var bgOpRow = makeRow('Opacity');
                bgOpRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.08, function(v) { draft.fillOpacity = v; }));
                body.appendChild(bgOpRow.row);

            // ---- FIBONACCI ----
            } else if (d.type === 'fibonacci') {
                addSectionHeading('TREND LINE');
                addLineRow(body);
                addWidthRow(body);
                var extRow = makeRow('Extend');
                extRow.ctrl.appendChild(makeSelect(["Don't extend", 'Left', 'Right', 'Both'], draft.extend || "Don't extend", function(v) { draft.extend = v; }));
                body.appendChild(extRow.row);
                addSectionHeading('LEVELS');
                var fibLevels = draft.fibLevelValues || _FIB_LEVELS.slice();
                var fibColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : _getFibColors();
                var fibEnabled = draft.fibEnabled || [];
                for (var fi = 0; fi < fibLevels.length; fi++) {
                    (function(idx) {
                        var fRow = makeRow('');
                        var enCb = makeCheckbox(fibEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = fibLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        });
                        fRow.ctrl.appendChild(enCb);
                        var levelInp = document.createElement('input');
                        levelInp.type = 'number'; levelInp.step = '0.001';
                        levelInp.className = 'ts-input ts-input-sm';
                        levelInp.value = fibLevels[idx].toFixed(3);
                        levelInp.addEventListener('input', function() {
                            if (!draft.fibLevelValues) draft.fibLevelValues = fibLevels.slice();
                            draft.fibLevelValues[idx] = parseFloat(levelInp.value) || 0;
                        });
                        levelInp.addEventListener('keydown', function(e) { e.stopPropagation(); });
                        fRow.ctrl.appendChild(levelInp);
                        fRow.ctrl.appendChild(makeColorSwatch(fibColors[idx] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) draft.fibColors = fibColors.slice();
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(fRow.row);
                    })(fi);
                }

            // ---- FIB EXTENSION ----
            } else if (d.type === 'fib_extension') {
                addSectionHeading('TREND LINE');
                addLineRow(body);
                addWidthRow(body);
                var extRow = makeRow('Extend');
                extRow.ctrl.appendChild(makeSelect(["Don't extend", 'Left', 'Right', 'Both'], draft.extend || "Don't extend", function(v) { draft.extend = v; }));
                body.appendChild(extRow.row);
                addSectionHeading('LEVELS');
                var extDefLevels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1, 1.618, 2.618, 4.236];
                var fibLevels = (draft.fibLevelValues && draft.fibLevelValues.length) ? draft.fibLevelValues : extDefLevels;
                var fibColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : _getFibColors();
                var fibEnabled = draft.fibEnabled || [];
                for (var fi = 0; fi < fibLevels.length; fi++) {
                    (function(idx) {
                        var fRow = makeRow('');
                        var enCb = makeCheckbox(fibEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = fibLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        });
                        fRow.ctrl.appendChild(enCb);
                        var levelInp = document.createElement('input');
                        levelInp.type = 'number'; levelInp.step = '0.001';
                        levelInp.className = 'ts-input ts-input-sm';
                        levelInp.value = fibLevels[idx].toFixed(3);
                        levelInp.addEventListener('input', function() {
                            if (!draft.fibLevelValues) draft.fibLevelValues = fibLevels.slice();
                            draft.fibLevelValues[idx] = parseFloat(levelInp.value) || 0;
                        });
                        levelInp.addEventListener('keydown', function(e) { e.stopPropagation(); });
                        fRow.ctrl.appendChild(levelInp);
                        fRow.ctrl.appendChild(makeColorSwatch(fibColors[idx % fibColors.length] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) draft.fibColors = fibColors.slice();
                            while (draft.fibColors.length <= idx) draft.fibColors.push(_drawDefaults.color);
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(fRow.row);
                    })(fi);
                }
                addSectionHeading('BACKGROUND');
                var bgEnRow = makeRow('Background');
                bgEnRow.ctrl.appendChild(makeCheckbox(draft.fillEnabled !== false, function(v) { draft.fillEnabled = v; }));
                bgEnRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(bgEnRow.row);
                var bgOpRow = makeRow('Opacity');
                bgOpRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.06, function(v) { draft.fillOpacity = v; }));
                body.appendChild(bgOpRow.row);

            // ---- FIB CHANNEL ----
            } else if (d.type === 'fib_channel') {
                addSectionHeading('BORDER');
                addLineRow(body);
                addWidthRow(body);
                var extRow = makeRow('Extend');
                extRow.ctrl.appendChild(makeSelect(["Don't extend", 'Left', 'Right', 'Both'], draft.extend || "Don't extend", function(v) { draft.extend = v; }));
                body.appendChild(extRow.row);
                addSectionHeading('LEVELS');
                var fibLevels = draft.fibLevelValues || _FIB_LEVELS.slice();
                var fibColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : _getFibColors();
                var fibEnabled = draft.fibEnabled || [];
                for (var fi = 0; fi < fibLevels.length; fi++) {
                    (function(idx) {
                        var fRow = makeRow('');
                        fRow.ctrl.appendChild(makeCheckbox(fibEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = fibLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        var levelInp = document.createElement('input');
                        levelInp.type = 'number'; levelInp.step = '0.001';
                        levelInp.className = 'ts-input ts-input-sm';
                        levelInp.value = fibLevels[idx].toFixed(3);
                        levelInp.addEventListener('input', function() {
                            if (!draft.fibLevelValues) draft.fibLevelValues = fibLevels.slice();
                            draft.fibLevelValues[idx] = parseFloat(levelInp.value) || 0;
                        });
                        levelInp.addEventListener('keydown', function(e) { e.stopPropagation(); });
                        fRow.ctrl.appendChild(levelInp);
                        fRow.ctrl.appendChild(makeColorSwatch(fibColors[idx] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) draft.fibColors = fibColors.slice();
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(fRow.row);
                    })(fi);
                }
                addSectionHeading('BACKGROUND');
                var bgEnRow = makeRow('Background');
                bgEnRow.ctrl.appendChild(makeCheckbox(draft.fillEnabled !== false, function(v) { draft.fillEnabled = v; }));
                bgEnRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(bgEnRow.row);
                var bgOpRow = makeRow('Opacity');
                bgOpRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.04, function(v) { draft.fillOpacity = v; }));
                body.appendChild(bgOpRow.row);

            // ---- FIB FAN ----
            } else if (d.type === 'fib_fan') {
                addSectionHeading('TREND LINE');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('LEVELS');
                var fibLevels = draft.fibLevelValues || _FIB_LEVELS.slice();
                var fibColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : _getFibColors();
                var fibEnabled = draft.fibEnabled || [];
                for (var fi = 0; fi < fibLevels.length; fi++) {
                    (function(idx) {
                        var fRow = makeRow('');
                        fRow.ctrl.appendChild(makeCheckbox(fibEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = fibLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        var levelInp = document.createElement('input');
                        levelInp.type = 'number'; levelInp.step = '0.001';
                        levelInp.className = 'ts-input ts-input-sm';
                        levelInp.value = fibLevels[idx].toFixed(3);
                        levelInp.addEventListener('input', function() {
                            if (!draft.fibLevelValues) draft.fibLevelValues = fibLevels.slice();
                            draft.fibLevelValues[idx] = parseFloat(levelInp.value) || 0;
                        });
                        levelInp.addEventListener('keydown', function(e) { e.stopPropagation(); });
                        fRow.ctrl.appendChild(levelInp);
                        fRow.ctrl.appendChild(makeColorSwatch(fibColors[idx] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) draft.fibColors = fibColors.slice();
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(fRow.row);
                    })(fi);
                }
                addSectionHeading('BACKGROUND');
                var bgEnRow = makeRow('Fill between fan lines');
                bgEnRow.ctrl.appendChild(makeCheckbox(draft.fillEnabled !== false, function(v) { draft.fillEnabled = v; }));
                body.appendChild(bgEnRow.row);
                var bgColRow = makeRow('Color');
                bgColRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(bgColRow.row);
                var bgOpRow = makeRow('Opacity');
                bgOpRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.03, function(v) { draft.fillOpacity = v; }));
                body.appendChild(bgOpRow.row);

            // ---- FIB ARC ----
            } else if (d.type === 'fib_arc') {
                addSectionHeading('TREND LINE');
                addLineRow(body);
                addWidthRow(body);
                var tlRow = makeRow('Show trend line');
                tlRow.ctrl.appendChild(makeCheckbox(draft.showTrendLine !== false, function(v) { draft.showTrendLine = v; }));
                body.appendChild(tlRow.row);
                addSectionHeading('LEVELS');
                var fibLevels = draft.fibLevelValues || _FIB_LEVELS.slice();
                var fibColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : _getFibColors();
                var fibEnabled = draft.fibEnabled || [];
                for (var fi = 0; fi < fibLevels.length; fi++) {
                    (function(idx) {
                        var fRow = makeRow('');
                        fRow.ctrl.appendChild(makeCheckbox(fibEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = fibLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        var levelInp = document.createElement('input');
                        levelInp.type = 'number'; levelInp.step = '0.001';
                        levelInp.className = 'ts-input ts-input-sm';
                        levelInp.value = fibLevels[idx].toFixed(3);
                        levelInp.addEventListener('input', function() {
                            if (!draft.fibLevelValues) draft.fibLevelValues = fibLevels.slice();
                            draft.fibLevelValues[idx] = parseFloat(levelInp.value) || 0;
                        });
                        levelInp.addEventListener('keydown', function(e) { e.stopPropagation(); });
                        fRow.ctrl.appendChild(levelInp);
                        fRow.ctrl.appendChild(makeColorSwatch(fibColors[idx] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) draft.fibColors = fibColors.slice();
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(fRow.row);
                    })(fi);
                }

            // ---- FIB CIRCLE ----
            } else if (d.type === 'fib_circle') {
                addSectionHeading('TREND LINE');
                addLineRow(body);
                addWidthRow(body);
                var tlRow = makeRow('Show trend line');
                tlRow.ctrl.appendChild(makeCheckbox(draft.showTrendLine !== false, function(v) { draft.showTrendLine = v; }));
                body.appendChild(tlRow.row);
                addSectionHeading('LEVELS');
                var fibLevels = draft.fibLevelValues || _FIB_LEVELS.slice();
                var fibColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : _getFibColors();
                var fibEnabled = draft.fibEnabled || [];
                for (var fi = 0; fi < fibLevels.length; fi++) {
                    (function(idx) {
                        var fRow = makeRow('');
                        fRow.ctrl.appendChild(makeCheckbox(fibEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = fibLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        var levelInp = document.createElement('input');
                        levelInp.type = 'number'; levelInp.step = '0.001';
                        levelInp.className = 'ts-input ts-input-sm';
                        levelInp.value = fibLevels[idx].toFixed(3);
                        levelInp.addEventListener('input', function() {
                            if (!draft.fibLevelValues) draft.fibLevelValues = fibLevels.slice();
                            draft.fibLevelValues[idx] = parseFloat(levelInp.value) || 0;
                        });
                        levelInp.addEventListener('keydown', function(e) { e.stopPropagation(); });
                        fRow.ctrl.appendChild(levelInp);
                        fRow.ctrl.appendChild(makeColorSwatch(fibColors[idx] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) draft.fibColors = fibColors.slice();
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(fRow.row);
                    })(fi);
                }

            // ---- FIB WEDGE ----
            } else if (d.type === 'fib_wedge') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('LEVELS');
                var fibLevels = draft.fibLevelValues || _FIB_LEVELS.slice();
                var fibColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : _getFibColors();
                var fibEnabled = draft.fibEnabled || [];
                for (var fi = 0; fi < fibLevels.length; fi++) {
                    (function(idx) {
                        var fRow = makeRow('');
                        fRow.ctrl.appendChild(makeCheckbox(fibEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = fibLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        var levelInp = document.createElement('input');
                        levelInp.type = 'number'; levelInp.step = '0.001';
                        levelInp.className = 'ts-input ts-input-sm';
                        levelInp.value = fibLevels[idx].toFixed(3);
                        levelInp.addEventListener('input', function() {
                            if (!draft.fibLevelValues) draft.fibLevelValues = fibLevels.slice();
                            draft.fibLevelValues[idx] = parseFloat(levelInp.value) || 0;
                        });
                        levelInp.addEventListener('keydown', function(e) { e.stopPropagation(); });
                        fRow.ctrl.appendChild(levelInp);
                        fRow.ctrl.appendChild(makeColorSwatch(fibColors[idx] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) draft.fibColors = fibColors.slice();
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(fRow.row);
                    })(fi);
                }
                addSectionHeading('BACKGROUND');
                var bgEnRow = makeRow('Background');
                bgEnRow.ctrl.appendChild(makeCheckbox(draft.fillEnabled !== false, function(v) { draft.fillEnabled = v; }));
                bgEnRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(bgEnRow.row);
                var bgOpRow = makeRow('Opacity');
                bgOpRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.04, function(v) { draft.fillOpacity = v; }));
                body.appendChild(bgOpRow.row);

            // ---- PITCHFAN ----
            } else if (d.type === 'pitchfan') {
                addSectionHeading('LINES');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('MEDIAN');
                var medRow = makeRow('Show median');
                medRow.ctrl.appendChild(makeCheckbox(draft.showMedian !== false, function(v) { draft.showMedian = v; }));
                body.appendChild(medRow.row);
                var medColorRow = makeRow('Median color');
                medColorRow.ctrl.appendChild(makeColorSwatch(draft.medianColor || draft.color || _drawDefaults.color, function(c) { draft.medianColor = c; }));
                body.appendChild(medColorRow.row);
                addSectionHeading('FAN LEVELS');
                var pfLevels = [0.236, 0.382, 0.5, 0.618, 0.786];
                var fibLevels = (draft.fibLevelValues && draft.fibLevelValues.length) ? draft.fibLevelValues : pfLevels;
                var fibColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : _getFibColors();
                var fibEnabled = draft.fibEnabled || [];
                for (var fi = 0; fi < fibLevels.length; fi++) {
                    (function(idx) {
                        var fRow = makeRow('');
                        fRow.ctrl.appendChild(makeCheckbox(fibEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = fibLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        var levelInp = document.createElement('input');
                        levelInp.type = 'number'; levelInp.step = '0.001';
                        levelInp.className = 'ts-input ts-input-sm';
                        levelInp.value = fibLevels[idx].toFixed(3);
                        levelInp.addEventListener('input', function() {
                            if (!draft.fibLevelValues) draft.fibLevelValues = fibLevels.slice();
                            draft.fibLevelValues[idx] = parseFloat(levelInp.value) || 0;
                        });
                        levelInp.addEventListener('keydown', function(e) { e.stopPropagation(); });
                        fRow.ctrl.appendChild(levelInp);
                        fRow.ctrl.appendChild(makeColorSwatch(fibColors[idx] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) draft.fibColors = fibColors.slice();
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(fRow.row);
                    })(fi);
                }

            // ---- FIB TIME ZONE ----
            } else if (d.type === 'fib_timezone') {
                addSectionHeading('TREND LINE');
                addLineRow(body);
                addWidthRow(body);
                var tlRow = makeRow('Show trend line');
                tlRow.ctrl.appendChild(makeCheckbox(draft.showTrendLine !== false, function(v) { draft.showTrendLine = v; }));
                body.appendChild(tlRow.row);
                addSectionHeading('TIME ZONE LINES');
                var tzNums = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144];
                var tzColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : _getFibColors();
                var tzEnabled = draft.fibEnabled || [];
                for (var fi = 0; fi < tzNums.length; fi++) {
                    (function(idx) {
                        var fRow = makeRow(String(tzNums[idx]));
                        fRow.ctrl.appendChild(makeCheckbox(tzEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = tzNums.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        fRow.ctrl.appendChild(makeColorSwatch(tzColors[idx % tzColors.length] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) {
                                draft.fibColors = [];
                                for (var ci = 0; ci < tzNums.length; ci++) draft.fibColors.push(tzColors[ci % tzColors.length] || _drawDefaults.color);
                            }
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(fRow.row);
                    })(fi);
                }

            // ---- MEASURE ----
            } else if (d.type === 'fib_time') {
                addSectionHeading('TREND LINE');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('LEVELS');
                var ftDefLevels = [0, 0.382, 0.5, 0.618, 1, 1.382, 1.618, 2, 2.618, 4.236];
                var ftLevels = (draft.fibLevelValues && draft.fibLevelValues.length) ? draft.fibLevelValues : ftDefLevels;
                var ftColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : _getFibColors();
                var ftEnabled = draft.fibEnabled || [];
                for (var fi = 0; fi < ftLevels.length; fi++) {
                    (function(idx) {
                        var fRow = makeRow(ftLevels[idx].toFixed(3));
                        fRow.ctrl.appendChild(makeCheckbox(ftEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = ftLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        fRow.ctrl.appendChild(makeColorSwatch(ftColors[idx % ftColors.length] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) {
                                draft.fibColors = [];
                                for (var ci = 0; ci < ftLevels.length; ci++) draft.fibColors.push(ftColors[ci % ftColors.length] || _drawDefaults.color);
                            }
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(fRow.row);
                    })(fi);
                }

            // ---- FIB SPIRAL ----
            } else if (d.type === 'fib_spiral') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);

            // ---- GANN BOX ----
            } else if (d.type === 'gann_box') {
                addSectionHeading('BORDER');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('LEVELS');
                var gbDefLevels = [0.25, 0.5, 0.75];
                var gbLevels = draft.gannLevels || gbDefLevels;
                var gbColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : [];
                var gbEnabled = draft.fibEnabled || [];
                for (var gi = 0; gi < gbLevels.length; gi++) {
                    (function(idx) {
                        var gRow = makeRow(gbLevels[idx].toFixed(3));
                        gRow.ctrl.appendChild(makeCheckbox(gbEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = gbLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        gRow.ctrl.appendChild(makeColorSwatch(gbColors[idx] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) { draft.fibColors = []; for (var ci = 0; ci < gbLevels.length; ci++) draft.fibColors.push(_drawDefaults.color); }
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(gRow.row);
                    })(gi);
                }
                addSectionHeading('BACKGROUND');
                var fillRow = makeRow('Fill');
                fillRow.ctrl.appendChild(makeCheckbox(draft.fillEnabled !== false, function(v) { draft.fillEnabled = v; }));
                body.appendChild(fillRow.row);
                var bgColRow = makeRow('Color');
                bgColRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(bgColRow.row);
                var opRow = makeRow('Opacity');
                opRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.03, function(v) { draft.fillOpacity = v; }));
                body.appendChild(opRow.row);

            // ---- GANN SQUARE FIXED ----
            } else if (d.type === 'gann_square_fixed') {
                addSectionHeading('BORDER');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('LEVELS');
                var gsfDefLevels = [0.25, 0.5, 0.75];
                var gsfLevels = draft.gannLevels || gsfDefLevels;
                var gsfColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : [];
                var gsfEnabled = draft.fibEnabled || [];
                for (var gi = 0; gi < gsfLevels.length; gi++) {
                    (function(idx) {
                        var gRow = makeRow(gsfLevels[idx].toFixed(3));
                        gRow.ctrl.appendChild(makeCheckbox(gsfEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = gsfLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        gRow.ctrl.appendChild(makeColorSwatch(gsfColors[idx] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) { draft.fibColors = []; for (var ci = 0; ci < gsfLevels.length; ci++) draft.fibColors.push(_drawDefaults.color); }
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(gRow.row);
                    })(gi);
                }
                addSectionHeading('BACKGROUND');
                var fillRow = makeRow('Fill');
                fillRow.ctrl.appendChild(makeCheckbox(draft.fillEnabled !== false, function(v) { draft.fillEnabled = v; }));
                body.appendChild(fillRow.row);
                var bgColRow = makeRow('Color');
                bgColRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(bgColRow.row);
                var opRow = makeRow('Opacity');
                opRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.03, function(v) { draft.fillOpacity = v; }));
                body.appendChild(opRow.row);

            // ---- GANN SQUARE ----
            } else if (d.type === 'gann_square') {
                addSectionHeading('BORDER');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('LEVELS');
                var gsDefLevels = [0.25, 0.5, 0.75];
                var gsLevels = draft.gannLevels || gsDefLevels;
                var gsColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : [];
                var gsEnabled = draft.fibEnabled || [];
                for (var gi = 0; gi < gsLevels.length; gi++) {
                    (function(idx) {
                        var gRow = makeRow(gsLevels[idx].toFixed(3));
                        gRow.ctrl.appendChild(makeCheckbox(gsEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = gsLevels.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        gRow.ctrl.appendChild(makeColorSwatch(gsColors[idx] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) { draft.fibColors = []; for (var ci = 0; ci < gsLevels.length; ci++) draft.fibColors.push(_drawDefaults.color); }
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(gRow.row);
                    })(gi);
                }
                addSectionHeading('BACKGROUND');
                var fillRow = makeRow('Fill');
                fillRow.ctrl.appendChild(makeCheckbox(draft.fillEnabled !== false, function(v) { draft.fillEnabled = v; }));
                body.appendChild(fillRow.row);
                var bgColRow = makeRow('Color');
                bgColRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(bgColRow.row);
                var opRow = makeRow('Opacity');
                opRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.03, function(v) { draft.fillOpacity = v; }));
                body.appendChild(opRow.row);

            // ---- GANN FAN ----
            } else if (d.type === 'gann_fan') {
                addSectionHeading('LINES');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('FAN LEVELS');
                var gfAngleNames = ['1\u00d78', '1\u00d74', '1\u00d73', '1\u00d72', '1\u00d71', '2\u00d71', '3\u00d71', '4\u00d71', '8\u00d71'];
                var gfColors = (draft.fibColors && draft.fibColors.length) ? draft.fibColors : [];
                var gfEnabled = draft.fibEnabled || [];
                for (var gi = 0; gi < gfAngleNames.length; gi++) {
                    (function(idx) {
                        var gRow = makeRow(gfAngleNames[idx]);
                        gRow.ctrl.appendChild(makeCheckbox(gfEnabled[idx] !== false, function(v) {
                            if (!draft.fibEnabled) draft.fibEnabled = gfAngleNames.map(function() { return true; });
                            draft.fibEnabled[idx] = v;
                        }));
                        gRow.ctrl.appendChild(makeColorSwatch(gfColors[idx] || _drawDefaults.color, function(c) {
                            if (!draft.fibColors) { draft.fibColors = []; for (var ci = 0; ci < gfAngleNames.length; ci++) draft.fibColors.push(_drawDefaults.color); }
                            draft.fibColors[idx] = c;
                        }));
                        body.appendChild(gRow.row);
                    })(gi);
                }

            // ---- MEASURE ----
            } else if (d.type === 'measure') {
                addSectionHeading('COLORS');
                var upRow = makeRow('Up color');
                upRow.ctrl.appendChild(makeColorSwatch(draft.colorUp || _cssVar('--pywry-draw-measure-up', '#26a69a'), function(c) { draft.colorUp = c; }));
                body.appendChild(upRow.row);
                var dnRow = makeRow('Down color');
                dnRow.ctrl.appendChild(makeColorSwatch(draft.colorDown || _cssVar('--pywry-draw-measure-down', '#ef5350'), function(c) { draft.colorDown = c; }));
                body.appendChild(dnRow.row);
                var bgOpRow = makeRow('Opacity');
                bgOpRow.ctrl.appendChild(makeOpacityInput(draft.fillOpacity !== undefined ? draft.fillOpacity : 0.08, function(v) { draft.fillOpacity = v; }));
                body.appendChild(bgOpRow.row);
                addSectionHeading('LABEL');
                var mFsRow = makeRow('Font size');
                mFsRow.ctrl.appendChild(makeSelect([{value:10,label:'10'},{value:11,label:'11'},{value:12,label:'12'},{value:13,label:'13'},{value:14,label:'14'},{value:16,label:'16'}], draft.fontSize || 12, function(v) { draft.fontSize = parseInt(v); }));
                body.appendChild(mFsRow.row);

            // ---- TEXT ----
            } else if (d.type === 'text') {
                addSectionHeading('TEXT');
                var tColorRow = makeRow('Color');
                tColorRow.ctrl.appendChild(makeColorSwatch(draft.color || _drawDefaults.color, function(c) { draft.color = c; }));
                body.appendChild(tColorRow.row);
                var fsRow = makeRow('Font size');
                fsRow.ctrl.appendChild(makeSelect([{value:10,label:'10'},{value:12,label:'12'},{value:14,label:'14'},{value:16,label:'16'},{value:18,label:'18'},{value:20,label:'20'},{value:24,label:'24'},{value:28,label:'28'}], draft.fontSize || 14, function(v) { draft.fontSize = parseInt(v); }));
                body.appendChild(fsRow.row);
                var boldRow = makeRow('Bold');
                boldRow.ctrl.appendChild(makeCheckbox(!!draft.bold, function(v) { draft.bold = v; }));
                body.appendChild(boldRow.row);
                var italicRow = makeRow('Italic');
                italicRow.ctrl.appendChild(makeCheckbox(!!draft.italic, function(v) { draft.italic = v; }));
                body.appendChild(italicRow.row);
                addSectionHeading('BACKGROUND');
                var bgEnRow = makeRow('Background');
                bgEnRow.ctrl.appendChild(makeCheckbox(!!draft.bgEnabled, function(v) { draft.bgEnabled = v; }));
                bgEnRow.ctrl.appendChild(makeColorSwatch(draft.bgColor || '#2a2e39', function(c) { draft.bgColor = c; }));
                body.appendChild(bgEnRow.row);
                var bgOpRow = makeRow('Opacity');
                bgOpRow.ctrl.appendChild(makeOpacityInput(draft.bgOpacity !== undefined ? draft.bgOpacity : 0.7, function(v) { draft.bgOpacity = v; }));
                body.appendChild(bgOpRow.row);

            // ---- BRUSH ----
            } else if (d.type === 'brush') {
                addSectionHeading('BRUSH');
                var cRow = makeRow('Color');
                cRow.ctrl.appendChild(makeColorSwatch(draft.color || _drawDefaults.color, function(c) { draft.color = c; }));
                body.appendChild(cRow.row);
                var wRow = makeRow('Width');
                wRow.ctrl.appendChild(makeSelect([{value:1,label:'1px'},{value:2,label:'2px'},{value:3,label:'3px'},{value:4,label:'4px'},{value:5,label:'5px'},{value:8,label:'8px'},{value:12,label:'12px'}], draft.lineWidth || 2, function(v) { draft.lineWidth = parseInt(v); }));
                body.appendChild(wRow.row);
                var opRow = makeRow('Opacity');
                opRow.ctrl.appendChild(makeOpacityInput(draft.opacity !== undefined ? draft.opacity : 1.0, function(v) { draft.opacity = v; }));
                body.appendChild(opRow.row);

            // ---- HIGHLIGHTER ----
            } else if (d.type === 'highlighter') {
                addSectionHeading('HIGHLIGHTER');
                var cRow = makeRow('Color');
                cRow.ctrl.appendChild(makeColorSwatch(draft.color || '#FFEB3B', function(c) { draft.color = c; }));
                body.appendChild(cRow.row);
                var wRow = makeRow('Width');
                wRow.ctrl.appendChild(makeSelect([{value:5,label:'5px'},{value:8,label:'8px'},{value:10,label:'10px'},{value:15,label:'15px'},{value:20,label:'20px'}], draft.lineWidth || 10, function(v) { draft.lineWidth = parseInt(v); }));
                body.appendChild(wRow.row);
                var opRow = makeRow('Opacity');
                opRow.ctrl.appendChild(makeOpacityInput(draft.opacity !== undefined ? draft.opacity : 0.4, function(v) { draft.opacity = v; }));
                body.appendChild(opRow.row);

            // ---- ARROW MARKER (filled shape) ----
            } else if (d.type === 'arrow_marker') {
                addSectionHeading('FILL');
                var fRow = makeRow('Fill color');
                fRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(fRow.row);
                addSectionHeading('BORDER');
                var brdRow = makeRow('Border color');
                brdRow.ctrl.appendChild(makeColorSwatch(draft.borderColor || draft.color || _drawDefaults.color, function(c) { draft.borderColor = c; }));
                body.appendChild(brdRow.row);
                addSectionHeading('TEXT');
                var tcRow = makeRow('Text color');
                tcRow.ctrl.appendChild(makeColorSwatch(draft.textColor || draft.color || _drawDefaults.color, function(c) { draft.textColor = c; }));
                body.appendChild(tcRow.row);
                var fsRow = makeRow('Font size');
                fsRow.ctrl.appendChild(makeSelect([{value:10,label:'10'},{value:12,label:'12'},{value:14,label:'14'},{value:16,label:'16'},{value:18,label:'18'},{value:20,label:'20'},{value:24,label:'24'},{value:30,label:'30'}], draft.fontSize || 16, function(v) { draft.fontSize = parseInt(v); }));
                body.appendChild(fsRow.row);
                var bRow = makeRow('Bold');
                bRow.ctrl.appendChild(makeCheckbox(!!draft.bold, function(v) { draft.bold = v; }));
                body.appendChild(bRow.row);
                var iRow = makeRow('Italic');
                iRow.ctrl.appendChild(makeCheckbox(!!draft.italic, function(v) { draft.italic = v; }));
                body.appendChild(iRow.row);

            // ---- ARROW (line with arrowhead) ----
            } else if (d.type === 'arrow') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);
                var styRow = makeRow('Line style');
                styRow.ctrl.appendChild(makeSelect([{value:0,label:'Solid'},{value:1,label:'Dashed'},{value:2,label:'Dotted'}], draft.lineStyle || 0, function(v) { draft.lineStyle = parseInt(v); }));
                body.appendChild(styRow.row);

            // ---- ARROW MARKS (up/down/left/right) ----
            } else if (d.type === 'arrow_mark_up' || d.type === 'arrow_mark_down' || d.type === 'arrow_mark_left' || d.type === 'arrow_mark_right') {
                addSectionHeading('FILL');
                var fRow = makeRow('Fill color');
                fRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || draft.color || _drawDefaults.color, function(c) { draft.fillColor = c; }));
                body.appendChild(fRow.row);
                addSectionHeading('BORDER');
                var brdRow = makeRow('Border color');
                brdRow.ctrl.appendChild(makeColorSwatch(draft.borderColor || draft.color || _drawDefaults.color, function(c) { draft.borderColor = c; }));
                body.appendChild(brdRow.row);
                addSectionHeading('TEXT');
                var tcRow = makeRow('Text color');
                tcRow.ctrl.appendChild(makeColorSwatch(draft.textColor || draft.color || _drawDefaults.color, function(c) { draft.textColor = c; }));
                body.appendChild(tcRow.row);
                var fsRow = makeRow('Font size');
                fsRow.ctrl.appendChild(makeSelect([{value:10,label:'10'},{value:12,label:'12'},{value:14,label:'14'},{value:16,label:'16'},{value:18,label:'18'},{value:20,label:'20'},{value:24,label:'24'},{value:30,label:'30'}], draft.fontSize || 16, function(v) { draft.fontSize = parseInt(v); }));
                body.appendChild(fsRow.row);
                var bRow = makeRow('Bold');
                bRow.ctrl.appendChild(makeCheckbox(!!draft.bold, function(v) { draft.bold = v; }));
                body.appendChild(bRow.row);
                var iRow = makeRow('Italic');
                iRow.ctrl.appendChild(makeCheckbox(!!draft.italic, function(v) { draft.italic = v; }));
                body.appendChild(iRow.row);

            // ---- TEXT/NOTES TOOLS (anchored_text, note, price_note, pin, callout, comment, price_label, signpost, flag_mark) ----
            } else if (['anchored_text', 'note', 'price_note', 'pin', 'callout', 'comment', 'price_label', 'signpost', 'flag_mark'].indexOf(d.type) !== -1) {
                // Pin, flag_mark, signpost: Style tab has only the marker color
                // Other text tools: Style tab has color, font, bold, italic, bg, border
                var _hoverTextTools = ['pin', 'flag_mark', 'signpost'];
                if (_hoverTextTools.indexOf(d.type) !== -1) {
                    addSectionHeading('MARKER');
                    var cRow = makeRow('Color');
                    cRow.ctrl.appendChild(makeColorSwatch(draft.markerColor || draft.color || _drawDefaults.color, function(c) { draft.markerColor = c; }));
                    body.appendChild(cRow.row);
                } else {
                    addSectionHeading('STYLE');
                    var cRow = makeRow('Color');
                    cRow.ctrl.appendChild(makeColorSwatch(draft.color || _drawDefaults.color, function(c) { draft.color = c; }));
                    body.appendChild(cRow.row);
                    var fsRow = makeRow('Font size');
                    fsRow.ctrl.appendChild(makeSelect([{value:10,label:'10'},{value:12,label:'12'},{value:14,label:'14'},{value:16,label:'16'},{value:18,label:'18'},{value:20,label:'20'},{value:24,label:'24'},{value:28,label:'28'}], draft.fontSize || 14, function(v) { draft.fontSize = parseInt(v); }));
                    body.appendChild(fsRow.row);
                    var bRow = makeRow('Bold');
                    bRow.ctrl.appendChild(makeCheckbox(!!draft.bold, function(v) { draft.bold = v; }));
                    body.appendChild(bRow.row);
                    var iRow = makeRow('Italic');
                    iRow.ctrl.appendChild(makeCheckbox(!!draft.italic, function(v) { draft.italic = v; }));
                    body.appendChild(iRow.row);
                    addSectionHeading('BACKGROUND');
                    var bgRow = makeRow('Background');
                    bgRow.ctrl.appendChild(makeCheckbox(draft.bgEnabled !== false, function(v) { draft.bgEnabled = v; }));
                    bgRow.ctrl.appendChild(makeColorSwatch(draft.bgColor || '#2a2e39', function(c) { draft.bgColor = c; }));
                    body.appendChild(bgRow.row);
                    var bdRow = makeRow('Border');
                    bdRow.ctrl.appendChild(makeCheckbox(!!draft.borderEnabled, function(v) { draft.borderEnabled = v; }));
                    bdRow.ctrl.appendChild(makeColorSwatch(draft.borderColor || draft.color || _drawDefaults.color, function(c) { draft.borderColor = c; }));
                    body.appendChild(bdRow.row);
                }

            // ---- CIRCLE / ELLIPSE ----
            } else if (d.type === 'circle' || d.type === 'ellipse') {
                addSectionHeading('BORDER');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('BACKGROUND');
                var fillRow = makeRow('Fill');
                fillRow.ctrl.appendChild(makeCheckbox(!!draft.fillColor, function(v) { draft.fillColor = v ? (draft.fillColor || 'rgba(41,98,255,0.2)') : ''; }));
                fillRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || 'rgba(41,98,255,0.2)', function(c) { draft.fillColor = c; }));
                body.appendChild(fillRow.row);

            // ---- TRIANGLE / ROTATED RECT ----
            } else if (d.type === 'triangle' || d.type === 'rotated_rect') {
                addSectionHeading('BORDER');
                addLineRow(body);
                addWidthRow(body);
                addSectionHeading('BACKGROUND');
                var fillRow = makeRow('Fill');
                fillRow.ctrl.appendChild(makeCheckbox(!!draft.fillColor, function(v) { draft.fillColor = v ? (draft.fillColor || 'rgba(41,98,255,0.2)') : ''; }));
                fillRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || 'rgba(41,98,255,0.2)', function(c) { draft.fillColor = c; }));
                body.appendChild(fillRow.row);

            // ---- PATH / POLYLINE ----
            } else if (d.type === 'path' || d.type === 'polyline') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);
                if (d.type === 'path') {
                    addSectionHeading('BACKGROUND');
                    var fillRow = makeRow('Fill');
                    fillRow.ctrl.appendChild(makeCheckbox(!!draft.fillColor, function(v) { draft.fillColor = v ? (draft.fillColor || 'rgba(41,98,255,0.2)') : ''; }));
                    fillRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || 'rgba(41,98,255,0.2)', function(c) { draft.fillColor = c; }));
                    body.appendChild(fillRow.row);
                }

            // ---- ARC / CURVE / DOUBLE CURVE ----
            } else if (d.type === 'shape_arc' || d.type === 'curve' || d.type === 'double_curve') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);

            // ---- LONG / SHORT POSITION ----
            } else if (d.type === 'long_position' || d.type === 'short_position') {
                addSectionHeading('COLORS');
                var profRow = makeRow('Profit color');
                profRow.ctrl.appendChild(makeColorSwatch(draft.profitColor || '#26a69a', function(c) { draft.profitColor = c; }));
                body.appendChild(profRow.row);
                var lossRow = makeRow('Stop color');
                lossRow.ctrl.appendChild(makeColorSwatch(draft.stopColor || '#ef5350', function(c) { draft.stopColor = c; }));
                body.appendChild(lossRow.row);
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);

            // ---- FORECAST / GHOST FEED ----
            } else if (d.type === 'forecast' || d.type === 'ghost_feed') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);

            // ---- BARS PATTERN / PROJECTION ----
            } else if (d.type === 'bars_pattern' || d.type === 'projection') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);

            // ---- ANCHORED VWAP ----
            } else if (d.type === 'anchored_vwap') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);

            // ---- FIXED RANGE VOLUME ----
            } else if (d.type === 'fixed_range_vol') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);

            // ---- PRICE RANGE / DATE RANGE / DATE+PRICE RANGE ----
            } else if (d.type === 'price_range' || d.type === 'date_range' || d.type === 'date_price_range') {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);
                if (d.type === 'date_price_range') {
                    addSectionHeading('BACKGROUND');
                    var fillRow = makeRow('Fill');
                    fillRow.ctrl.appendChild(makeColorSwatch(draft.fillColor || 'rgba(41,98,255,0.1)', function(c) { draft.fillColor = c; }));
                    body.appendChild(fillRow.row);
                }

            // ---- FALLBACK (any unknown type) ----
            } else {
                addSectionHeading('LINE');
                addLineRow(body);
                addWidthRow(body);
            }

        } else if (activeTab === 'Text' && d.type === 'text') {
            addSectionHeading('CONTENT');
            var tRow = makeRow('Text');
            tRow.ctrl.appendChild(makeTextInput(draft.text || '', function(v) { draft.text = v; }));
            body.appendChild(tRow.row);

        } else if (activeTab === 'Text' && (d.type === 'trendline' || d.type === 'ray' || d.type === 'extended_line')) {
            addSectionHeading('TEXT');
            var tRow = makeRow('Text');
            tRow.ctrl.appendChild(makeTextInput(draft.text || '', function(v) { draft.text = v; }));
            body.appendChild(tRow.row);
            var tColorRow = makeRow('Text color');
            tColorRow.ctrl.appendChild(makeColorSwatch(draft.textColor || draft.color || _drawDefaults.color, function(c) { draft.textColor = c; }));
            body.appendChild(tColorRow.row);
            var tSizeRow = makeRow('Font size');
            tSizeRow.ctrl.appendChild(makeSelect([{value:10,label:'10'},{value:12,label:'12'},{value:14,label:'14'},{value:16,label:'16'},{value:18,label:'18'},{value:20,label:'20'},{value:24,label:'24'}], draft.textFontSize || 12, function(v) { draft.textFontSize = parseInt(v); }));
            body.appendChild(tSizeRow.row);
            var tBoldRow = makeRow('Bold');
            tBoldRow.ctrl.appendChild(makeCheckbox(!!draft.textBold, function(v) { draft.textBold = v; }));
            body.appendChild(tBoldRow.row);
            var tItalicRow = makeRow('Italic');
            tItalicRow.ctrl.appendChild(makeCheckbox(!!draft.textItalic, function(v) { draft.textItalic = v; }));
            body.appendChild(tItalicRow.row);

        } else if (activeTab === 'Text' && (d.type === 'arrow_marker' || d.type === 'arrow' || d.type === 'arrow_mark_up' || d.type === 'arrow_mark_down' || d.type === 'arrow_mark_left' || d.type === 'arrow_mark_right')) {
            addSectionHeading('TEXT');
            var tRow = makeRow('Text');
            tRow.ctrl.appendChild(makeTextInput(draft.text || '', function(v) { draft.text = v; }));
            body.appendChild(tRow.row);

        } else if (activeTab === 'Text' && ['anchored_text', 'note', 'price_note', 'pin', 'callout', 'comment', 'price_label', 'signpost', 'flag_mark'].indexOf(d.type) !== -1) {
            var _hoverTextTools2 = ['pin', 'flag_mark', 'signpost'];
            if (_hoverTextTools2.indexOf(d.type) !== -1) {
                // TV-style Text tab: font row, textarea, background, border
                var fontRow = document.createElement('div');
                fontRow.style.cssText = 'display:flex;align-items:center;gap:8px;padding:8px 16px;';
                fontRow.appendChild(makeColorSwatch(draft.color || _drawDefaults.color, function(c) { draft.color = c; }));
                fontRow.appendChild(makeSelect([{value:10,label:'10'},{value:12,label:'12'},{value:14,label:'14'},{value:16,label:'16'},{value:18,label:'18'},{value:20,label:'20'},{value:24,label:'24'},{value:28,label:'28'}], draft.fontSize || 14, function(v) { draft.fontSize = parseInt(v); }));
                var boldBtn = document.createElement('button');
                boldBtn.textContent = 'B';
                boldBtn.className = 'ts-btn' + (draft.bold ? ' active' : '');
                boldBtn.style.cssText = 'font-weight:bold;min-width:28px;height:28px;border:1px solid rgba(255,255,255,0.2);border-radius:4px;background:' + (draft.bold ? 'rgba(255,255,255,0.15)' : 'transparent') + ';color:inherit;cursor:pointer;';
                boldBtn.addEventListener('click', function() {
                    draft.bold = !draft.bold;
                    boldBtn.style.background = draft.bold ? 'rgba(255,255,255,0.15)' : 'transparent';
                });
                fontRow.appendChild(boldBtn);
                var italicBtn = document.createElement('button');
                italicBtn.textContent = 'I';
                italicBtn.className = 'ts-btn' + (draft.italic ? ' active' : '');
                italicBtn.style.cssText = 'font-style:italic;min-width:28px;height:28px;border:1px solid rgba(255,255,255,0.2);border-radius:4px;background:' + (draft.italic ? 'rgba(255,255,255,0.15)' : 'transparent') + ';color:inherit;cursor:pointer;';
                italicBtn.addEventListener('click', function() {
                    draft.italic = !draft.italic;
                    italicBtn.style.background = draft.italic ? 'rgba(255,255,255,0.15)' : 'transparent';
                });
                fontRow.appendChild(italicBtn);
                body.appendChild(fontRow);

                var ta = document.createElement('textarea');
                ta.className = 'ts-input ts-input-full tv-settings-textarea';
                ta.style.cssText = 'margin:8px 16px;min-height:80px;resize:vertical;border:2px solid #2962ff;border-radius:4px;background:#1e222d;color:inherit;padding:8px;font-family:inherit;font-size:14px;';
                ta.placeholder = 'Add text';
                ta.value = draft.text || '';
                ta.addEventListener('input', function() { draft.text = ta.value; });
                ta.addEventListener('keydown', function(e) { e.stopPropagation(); });
                body.appendChild(ta);

                var bgRow2 = makeRow('Background');
                bgRow2.ctrl.appendChild(makeCheckbox(draft.bgEnabled !== false, function(v) { draft.bgEnabled = v; }));
                bgRow2.ctrl.appendChild(makeColorSwatch(draft.bgColor || '#2a2e39', function(c) { draft.bgColor = c; }));
                body.appendChild(bgRow2.row);
                var bdRow2 = makeRow('Border');
                bdRow2.ctrl.appendChild(makeCheckbox(!!draft.borderEnabled, function(v) { draft.borderEnabled = v; }));
                bdRow2.ctrl.appendChild(makeColorSwatch(draft.borderColor || draft.color || _drawDefaults.color, function(c) { draft.borderColor = c; }));
                body.appendChild(bdRow2.row);
            } else {
                addSectionHeading('TEXT');
                var tRow = makeRow('Text');
                tRow.ctrl.appendChild(makeTextInput(draft.text || '', function(v) { draft.text = v; }));
                body.appendChild(tRow.row);
            }

        } else if (activeTab === 'Coordinates') {
            // Helper: make a bar index input from a time value
            function makeBarInput(tKey) {
                var entry = window.__PYWRY_TVCHARTS__ && window.__PYWRY_TVCHARTS__[chartId];
                var data = entry && entry.series && typeof entry.series.data === 'function' ? entry.series.data() : null;
                var barIdx = 0;
                if (data && data.length && draft[tKey]) {
                    for (var bi = 0; bi < data.length; bi++) {
                        if (data[bi].time >= draft[tKey]) { barIdx = bi; break; }
                    }
                    if (barIdx === 0 && data[data.length - 1].time < draft[tKey]) barIdx = data.length - 1;
                }
                var inp = document.createElement('input');
                inp.type = 'number';
                inp.className = 'ts-input';
                inp.value = barIdx;
                inp.min = '0';
                inp.max = data ? String(data.length - 1) : '0';
                inp.step = '1';
                inp.addEventListener('input', function() {
                    if (!data || !data.length) return;
                    var idx = Math.max(0, Math.min(parseInt(inp.value) || 0, data.length - 1));
                    draft[tKey] = data[idx].time;
                });
                inp.addEventListener('keydown', function(e) { e.stopPropagation(); });
                return inp;
            }

            if (d.type === 'hline') {
                addSectionHeading('PRICE');
                var pRow = makeRow('Price');
                pRow.ctrl.appendChild(makeNumberInput(draft.price || draft.p1 || 0, function(v) {
                    draft.price = v; draft.p1 = v;
                }));
                body.appendChild(pRow.row);
            } else if (d.type === 'trendline' || d.type === 'ray' || d.type === 'extended_line' || d.type === 'fibonacci' || d.type === 'measure' ||
                       d.type === 'fib_timezone' || d.type === 'fib_fan' || d.type === 'fib_arc' || d.type === 'fib_circle' ||
                       d.type === 'fib_spiral' || d.type === 'gann_box' || d.type === 'gann_square_fixed' || d.type === 'gann_square' || d.type === 'gann_fan' ||
                       d.type === 'arrow_marker' || d.type === 'arrow' || d.type === 'circle' || d.type === 'ellipse' || d.type === 'curve' ||
                       d.type === 'long_position' || d.type === 'short_position' || d.type === 'forecast' ||
                       d.type === 'bars_pattern' || d.type === 'ghost_feed' || d.type === 'projection' || d.type === 'fixed_range_vol' ||
                       d.type === 'price_range' || d.type === 'date_range' || d.type === 'date_price_range') {
                addSectionHeading('#1');
                var b1Row = makeRow('Bar');
                b1Row.ctrl.appendChild(makeBarInput('t1'));
                body.appendChild(b1Row.row);
                var p1Row = makeRow('Price');
                p1Row.ctrl.appendChild(makeNumberInput(draft.p1 || 0, function(v) { draft.p1 = v; }));
                body.appendChild(p1Row.row);
                addSectionHeading('#2');
                var b2Row = makeRow('Bar');
                b2Row.ctrl.appendChild(makeBarInput('t2'));
                body.appendChild(b2Row.row);
                var p2Row = makeRow('Price');
                p2Row.ctrl.appendChild(makeNumberInput(draft.p2 || 0, function(v) { draft.p2 = v; }));
                body.appendChild(p2Row.row);
            } else if (d.type === 'fib_extension' || d.type === 'fib_channel' || d.type === 'fib_wedge' || d.type === 'pitchfan' || d.type === 'fib_time' ||
                       d.type === 'rotated_rect' || d.type === 'triangle' || d.type === 'shape_arc' || d.type === 'double_curve') {
                addSectionHeading('#1');
                var b1Row = makeRow('Bar');
                b1Row.ctrl.appendChild(makeBarInput('t1'));
                body.appendChild(b1Row.row);
                var p1Row = makeRow('Price');
                p1Row.ctrl.appendChild(makeNumberInput(draft.p1 || 0, function(v) { draft.p1 = v; }));
                body.appendChild(p1Row.row);
                addSectionHeading('#2');
                var b2Row = makeRow('Bar');
                b2Row.ctrl.appendChild(makeBarInput('t2'));
                body.appendChild(b2Row.row);
                var p2Row = makeRow('Price');
                p2Row.ctrl.appendChild(makeNumberInput(draft.p2 || 0, function(v) { draft.p2 = v; }));
                body.appendChild(p2Row.row);
                addSectionHeading('#3');
                var b3Row = makeRow('Bar');
                b3Row.ctrl.appendChild(makeBarInput('t3'));
                body.appendChild(b3Row.row);
                var p3Row = makeRow('Price');
                p3Row.ctrl.appendChild(makeNumberInput(draft.p3 || 0, function(v) { draft.p3 = v; }));
                body.appendChild(p3Row.row);
            } else if (d.type === 'vline') {
                addSectionHeading('TIME');
                var vbRow = makeRow('Bar');
                vbRow.ctrl.appendChild(makeBarInput('t1'));
                body.appendChild(vbRow.row);
            } else if (d.type === 'crossline') {
                addSectionHeading('POSITION');
                var cbRow = makeRow('Bar');
                cbRow.ctrl.appendChild(makeBarInput('t1'));
                body.appendChild(cbRow.row);
                var pRow = makeRow('Price');
                pRow.ctrl.appendChild(makeNumberInput(draft.p1 || 0, function(v) { draft.p1 = v; }));
                body.appendChild(pRow.row);
            } else if (d.type === 'hray') {
                addSectionHeading('POSITION');
                var hbRow = makeRow('Bar');
                hbRow.ctrl.appendChild(makeBarInput('t1'));
                body.appendChild(hbRow.row);
                var pRow = makeRow('Price');
                pRow.ctrl.appendChild(makeNumberInput(draft.p1 || 0, function(v) { draft.p1 = v; }));
                body.appendChild(pRow.row);
            } else if (d.type === 'flat_channel') {
                addSectionHeading('LEVELS');
                var p1Row = makeRow('Upper level');
                p1Row.ctrl.appendChild(makeNumberInput(draft.p1 || 0, function(v) { draft.p1 = v; }));
                body.appendChild(p1Row.row);
                var p2Row = makeRow('Lower level');
                p2Row.ctrl.appendChild(makeNumberInput(draft.p2 || 0, function(v) { draft.p2 = v; }));
                body.appendChild(p2Row.row);
            } else if (d.type === 'regression_channel') {
                addSectionHeading('#1');
                var rb1 = makeRow('Bar');
                rb1.ctrl.appendChild(makeBarInput('t1'));
                body.appendChild(rb1.row);
                var rp1 = makeRow('Price');
                rp1.ctrl.appendChild(makeNumberInput(draft.p1 || 0, function(v) { draft.p1 = v; }));
                body.appendChild(rp1.row);
                addSectionHeading('#2');
                var rb2 = makeRow('Bar');
                rb2.ctrl.appendChild(makeBarInput('t2'));
                body.appendChild(rb2.row);
                var rp2 = makeRow('Price');
                rp2.ctrl.appendChild(makeNumberInput(draft.p2 || 0, function(v) { draft.p2 = v; }));
                body.appendChild(rp2.row);
            } else if (d.type === 'rect') {
                addSectionHeading('TOP-LEFT');
                var rb1 = makeRow('Bar');
                rb1.ctrl.appendChild(makeBarInput('t1'));
                body.appendChild(rb1.row);
                var p1Row = makeRow('Price');
                p1Row.ctrl.appendChild(makeNumberInput(draft.p1 || 0, function(v) { draft.p1 = v; }));
                body.appendChild(p1Row.row);
                addSectionHeading('BOTTOM-RIGHT');
                var rb2 = makeRow('Bar');
                rb2.ctrl.appendChild(makeBarInput('t2'));
                body.appendChild(rb2.row);
                var p2Row = makeRow('Price');
                p2Row.ctrl.appendChild(makeNumberInput(draft.p2 || 0, function(v) { draft.p2 = v; }));
                body.appendChild(p2Row.row);
            } else if (d.type === 'channel') {
                addSectionHeading('#1');
                var cb1 = makeRow('Bar');
                cb1.ctrl.appendChild(makeBarInput('t1'));
                body.appendChild(cb1.row);
                var cp1 = makeRow('Price');
                cp1.ctrl.appendChild(makeNumberInput(draft.p1 || 0, function(v) { draft.p1 = v; }));
                body.appendChild(cp1.row);
                addSectionHeading('#2');
                var cb2 = makeRow('Bar');
                cb2.ctrl.appendChild(makeBarInput('t2'));
                body.appendChild(cb2.row);
                var cp2 = makeRow('Price');
                cp2.ctrl.appendChild(makeNumberInput(draft.p2 || 0, function(v) { draft.p2 = v; }));
                body.appendChild(cp2.row);
                addSectionHeading('CHANNEL');
                var offRow = makeRow('Offset (px)');
                offRow.ctrl.appendChild(makeNumberInput(draft.offset || 30, function(v) { draft.offset = v; }));
                body.appendChild(offRow.row);
            } else if (d.type === 'brush' || d.type === 'highlighter' || d.type === 'path' || d.type === 'polyline') {
                addSectionHeading('POSITION');
                var noRow = document.createElement('div');
                noRow.className = 'tv-settings-row';
                noRow.style.cssText = 'color:var(--pywry-tvchart-text-muted,#787b86);font-size:12px;';
                noRow.textContent = 'Freeform drawing \u2014 drag to reposition.';
                body.appendChild(noRow);
            } else if (d.type === 'arrow_mark_up' || d.type === 'arrow_mark_down' || d.type === 'arrow_mark_left' || d.type === 'arrow_mark_right' || d.type === 'anchored_vwap') {
                addSectionHeading('POSITION');
                var abRow = makeRow('Bar');
                abRow.ctrl.appendChild(makeBarInput('t1'));
                body.appendChild(abRow.row);
                var apRow = makeRow('Price');
                apRow.ctrl.appendChild(makeNumberInput(draft.p1 || 0, function(v) { draft.p1 = v; }));
                body.appendChild(apRow.row);
            } else if (d.type === 'text') {
                addSectionHeading('POSITION');
                var tbRow = makeRow('Bar');
                tbRow.ctrl.appendChild(makeBarInput('t1'));
                body.appendChild(tbRow.row);
                var tpRow = makeRow('Price');
                tpRow.ctrl.appendChild(makeNumberInput(draft.p1 || 0, function(v) { draft.p1 = v; }));
                body.appendChild(tpRow.row);
            } else {
                if (draft.p1 !== undefined) {
                    var p1Row = makeRow('Price 1');
                    p1Row.ctrl.appendChild(makeNumberInput(draft.p1, function(v) { draft.p1 = v; }));
                    body.appendChild(p1Row.row);
                }
                if (draft.p2 !== undefined) {
                    var p2Row = makeRow('Price 2');
                    p2Row.ctrl.appendChild(makeNumberInput(draft.p2, function(v) { draft.p2 = v; }));
                    body.appendChild(p2Row.row);
                }
            }

        } else if (activeTab === 'Visibility') {
            addSectionHeading('TIME INTERVALS');
            addVisibilityIntervals(body);
            addSectionHeading('DRAWING');
            var hRow = makeRow('Hidden');
            hRow.ctrl.appendChild(makeCheckbox(!!draft.hidden, function(v) { draft.hidden = v; }));
            body.appendChild(hRow.row);
            var lkRow = makeRow('Locked');
            lkRow.ctrl.appendChild(makeCheckbox(!!draft.locked, function(v) { draft.locked = v; }));
            body.appendChild(lkRow.row);
        }
    }

    // Footer
    var footer = document.createElement('div');
    footer.className = 'tv-settings-footer';
    footer.style.cssText = 'position:relative;bottom:auto;left:auto;right:auto;';
    var cancelBtn = document.createElement('button');
    cancelBtn.className = 'ts-btn-cancel';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.addEventListener('click', function() { _tvHideDrawingSettings(); });
    footer.appendChild(cancelBtn);
    var okBtn = document.createElement('button');
    okBtn.className = 'ts-btn-ok';
    okBtn.textContent = 'Ok';
    okBtn.addEventListener('click', function() {
        // Apply draft onto original drawing
        Object.assign(d, draft);
        // Sync native price line for hline
        if (d.type === 'hline') {
            _tvSyncPriceLineColor(chartId, drawIdx, d.color || _drawDefaults.color);
            _tvSyncPriceLinePrice(chartId, drawIdx, d.price || d.p1);
        }
        _tvRenderDrawings(chartId);
        if (_floatingToolbar) {
            _tvHideFloatingToolbar();
            _tvShowFloatingToolbar(chartId, drawIdx);
        }
        _tvHideDrawingSettings();
    });
    footer.appendChild(okBtn);
    panel.appendChild(footer);

    renderTabs();
    renderBody();
    ds.uiLayer.appendChild(overlay);
}

