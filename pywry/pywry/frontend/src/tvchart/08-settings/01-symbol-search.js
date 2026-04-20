function _tvShowSymbolSearchDialog(chartId, options) {
    _tvHideSymbolSearch();
    var resolved = _tvResolveChartEntry(chartId);
    if (!resolved || !resolved.entry) return;
    chartId = resolved.chartId;
    var entry = resolved.entry;
    options = options || {};
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

    // Programmatic drive: pre-fill the search query and optionally
    // auto-select the first result (or a specific symbol match) when
    // the datafeed responds. Driven by `tvchart:symbol-search` callers
    // that pass `{query, autoSelect, symbolType, exchange}` (e.g. agent
    // tools).  ``symbolType`` / ``exchange`` pre-select the filter
    // dropdowns so the datafeed search is narrowed before it runs —
    // e.g. ``{query: "SPY", symbolType: "etf"}`` skips over SPYM.
    if (options.query) {
        var preQuery = String(options.query).trim();
        if (preQuery) {
            searchInput.value = preQuery;
            var autoSelect = options.autoSelect !== false;
            // Pre-select filter dropdowns (case-insensitive match against
            // option values).  Silently ignore unknown filter values so a
            // caller's ``symbolType: "etf"`` request doesn't break the
            // search when the datafeed exposes ``ETF`` instead.
            if (options.symbolType) {
                var wantType = String(options.symbolType).toLowerCase();
                for (var tsi = 0; tsi < typeSelect.options.length; tsi++) {
                    if (String(typeSelect.options[tsi].value).toLowerCase() === wantType) {
                        typeSelect.selectedIndex = tsi;
                        break;
                    }
                }
            }
            if (options.exchange) {
                var wantExch = String(options.exchange).toLowerCase();
                for (var esi = 0; esi < exchangeSelect.options.length; esi++) {
                    if (String(exchangeSelect.options[esi].value).toLowerCase() === wantExch) {
                        exchangeSelect.selectedIndex = esi;
                        break;
                    }
                }
            }
            // Optimistically advertise the requested ticker on the chart's
            // payload BEFORE the datafeed search round-trip completes.  Other
            // events that fire in the meantime (e.g. a `tvchart:interval-change`
            // dispatched by the same agent turn) read this field to decide
            // which symbol to refetch — without the optimistic update they
            // see the previous symbol and clobber the pending change with a
            // refetch of the old ticker.  ``selectSymbol`` re-confirms the
            // value once the resolve responds; if the search fails to find a
            // match the optimistic value is harmless because no data-request
            // ever fires.
            var optimisticTicker = preQuery.toUpperCase();
            if (optimisticTicker.indexOf(':') >= 0) {
                optimisticTicker = optimisticTicker.split(':').pop().trim();
            }
            if (entry && entry.payload) {
                entry.payload.title = optimisticTicker;
                if (entry.payload.series && Array.isArray(entry.payload.series) && entry.payload.series[0]) {
                    entry.payload.series[0].symbol = optimisticTicker;
                }
            }

            var prevRender = renderResults;
            // Wrap renderResults to auto-select on first non-empty results.
            var selected = false;
            // Pull the bare ticker from a symbol record — datafeed results
            // may carry a fully-qualified ``EXCHANGE:TICKER`` in ``ticker``
            // and the bare ticker in ``symbol`` / ``requestSymbol``.  Exact
            // match has to beat prefix match (``SPY`` → ``SPY``, not
            // ``SPYM``) even when the datafeed returns them alphabetically.
            function _bareTickerSearch(rec) {
                if (!rec) return '';
                var candidates = [rec.symbol, rec.requestSymbol, rec.ticker];
                for (var ci = 0; ci < candidates.length; ci++) {
                    var raw = String(candidates[ci] || '').toUpperCase();
                    if (!raw) continue;
                    if (raw.indexOf(':') >= 0) raw = raw.split(':').pop().trim();
                    if (raw) return raw;
                }
                return '';
            }
            renderResults = function() {
                prevRender();
                if (selected || !autoSelect || !searchResults.length) return;
                var match = null;
                for (var mi = 0; mi < searchResults.length; mi++) {
                    if (_bareTickerSearch(searchResults[mi]) === optimisticTicker) {
                        match = searchResults[mi];
                        break;
                    }
                }
                if (!match) {
                    for (var mj = 0; mj < searchResults.length; mj++) {
                        if (_bareTickerSearch(searchResults[mj]).indexOf(optimisticTicker) === 0) {
                            match = searchResults[mj];
                            break;
                        }
                    }
                }
                if (!match) match = searchResults[0];
                selected = true;
                // Re-sync the optimistic value with the actual selected match
                // — the auto-pick fallback may have chosen a different ticker
                // than the requested query.
                var resolvedTicker = (match.ticker || match.requestSymbol || match.symbol || '').toString().toUpperCase();
                if (resolvedTicker && entry && entry.payload) {
                    entry.payload.title = resolvedTicker;
                    if (entry.payload.series && Array.isArray(entry.payload.series) && entry.payload.series[0]) {
                        entry.payload.series[0].symbol = resolvedTicker;
                    }
                }
                selectSymbol(match);
            };
            requestSearch(preQuery);
        }
    }
}

