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

