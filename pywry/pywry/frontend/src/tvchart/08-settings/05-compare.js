function _tvShowComparePanel(chartId, options) {
    options = options || {};
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

    // Programmatic drive: pre-fill the search and auto-add the first
    // matching ticker.  Driven by ``tvchart:compare`` callers that pass
    // ``{query, autoAdd, symbolType, exchange}`` (e.g. the MCP
    // tvchart_compare tool).  ``symbolType`` / ``exchange`` narrow the
    // datafeed search before it runs — e.g. ``{query: "SPY", symbolType:
    // "etf"}`` skips over SPYM.  Mirrors the symbol-search auto-select
    // flow so the compare shows up in entry._compareSymbols before the
    // caller polls chart state.
    if (options.query) {
        var cmpQuery = String(options.query).trim();
        if (cmpQuery) {
            searchInput.value = cmpQuery;
            var autoAdd = options.autoAdd !== false;
            if (options.symbolType) {
                var wantCmpType = String(options.symbolType).toLowerCase();
                for (var ctsi = 0; ctsi < typeSelect.options.length; ctsi++) {
                    if (String(typeSelect.options[ctsi].value).toLowerCase() === wantCmpType) {
                        typeSelect.selectedIndex = ctsi;
                        break;
                    }
                }
            }
            if (options.exchange) {
                var wantCmpExch = String(options.exchange).toLowerCase();
                for (var cesi = 0; cesi < exchangeSelect.options.length; cesi++) {
                    if (String(exchangeSelect.options[cesi].value).toLowerCase() === wantCmpExch) {
                        exchangeSelect.selectedIndex = cesi;
                        break;
                    }
                }
            }
            var prevRenderCmp = renderSearchResults;
            var addedOnce = false;
            var targetTicker = cmpQuery.toUpperCase();
            if (targetTicker.indexOf(':') >= 0) {
                targetTicker = targetTicker.split(':').pop().trim();
            }
            // Pull the bare ticker from a symbol record — datafeed results
            // may carry a fully-qualified ``EXCHANGE:TICKER`` in ``ticker``
            // and the bare ticker in ``symbol`` / ``requestSymbol``.  Exact-
            // match needs to beat prefix-match (otherwise ``SPY`` finds
            // ``SPYM`` first just because ``SPYM`` sorted earlier).
            function _bareTicker(rec) {
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
            renderSearchResults = function() {
                prevRenderCmp();
                if (addedOnce || !autoAdd || !searchResults.length) return;
                var pick = null;
                for (var pi = 0; pi < searchResults.length; pi++) {
                    if (_bareTicker(searchResults[pi]) === targetTicker) {
                        pick = searchResults[pi];
                        break;
                    }
                }
                // No exact match → prefer results whose bare ticker
                // *starts with* the query, then fall back to the first
                // result.  Prevents ``SPY`` → ``SPYM`` just because the
                // datafeed returned them in alphabetical order.
                if (!pick) {
                    for (var pj = 0; pj < searchResults.length; pj++) {
                        if (_bareTicker(searchResults[pj]).indexOf(targetTicker) === 0) {
                            pick = searchResults[pj];
                            break;
                        }
                    }
                }
                if (!pick) pick = searchResults[0];
                addedOnce = true;
                addCompare(pick, 'same_percent');
                // Auto-close the panel after a programmatic add so the
                // MCP caller's confirmation flow doesn't leave an empty
                // search dialog sitting on top of the chart.
                setTimeout(function() { _tvHideComparePanel(); }, 0);
            };
            requestSearch(cmpQuery);
        }
    }
}

// ---------------------------------------------------------------------------
// Indicator Symbol Picker – shown when a binary indicator (Spread, Ratio,
// Product, Sum, Correlation) is added but no secondary series exists yet.
// ---------------------------------------------------------------------------
var _indicatorPickerOverlay = null;
var _indicatorPickerChartId = null;

