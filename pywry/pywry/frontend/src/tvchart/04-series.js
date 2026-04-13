function _tvIndicatorSourceSeriesIds(entry) {
    var keys = Object.keys(entry.seriesMap || {});
    var out = [];
    for (var i = 0; i < keys.length; i++) {
        var sid = keys[i];
        if (_activeIndicators[sid]) continue;
        if (sid.indexOf('ind_') === 0) continue;
        out.push(sid);
    }
    out.sort(function(a, b) {
        if (a === 'main') return -1;
        if (b === 'main') return 1;
        return String(a).localeCompare(String(b));
    });
    return out;
}

function _tvEnsurePayloadSeriesList(entry) {
    if (!entry) return [];
    if (!entry.payload) entry.payload = {};
    if (entry.payload.series && Array.isArray(entry.payload.series)) return entry.payload.series;

    entry.payload.series = [{
        seriesId: 'main',
        bars: entry.payload.bars || (entry._seriesRawData && entry._seriesRawData.main) || [],
        volume: entry.payload.volume || [],
        seriesType: entry.payload.seriesType || 'Candlestick',
        seriesOptions: entry.payload.seriesOptions || {},
    }];
    return entry.payload.series;
}

function _tvFindPayloadSeries(entry, seriesId) {
    var list = _tvEnsurePayloadSeriesList(entry);
    for (var i = 0; i < list.length; i++) {
        if (String(list[i].seriesId || 'main') === String(seriesId || 'main')) return list[i];
    }
    return null;
}

function _tvUpsertPayloadSeries(entry, seriesId, patch) {
    if (!entry) return;
    var sid = seriesId || 'main';
    var list = _tvEnsurePayloadSeriesList(entry);
    var row = _tvFindPayloadSeries(entry, sid);
    if (!row) {
        row = {
            seriesId: sid,
            bars: [],
            volume: [],
            seriesType: 'Line',
            seriesOptions: {},
        };
        list.push(row);
    }
    if (!patch || typeof patch !== 'object') return;
    var keys = Object.keys(patch);
    for (var i = 0; i < keys.length; i++) {
        var k = keys[i];
        row[k] = patch[k];
    }
}

function _tvRemovePayloadSeries(entry, seriesId) {
    if (!entry || !entry.payload || !entry.payload.series || !Array.isArray(entry.payload.series)) return;
    var sid = String(seriesId || 'main');
    entry.payload.series = entry.payload.series.filter(function(s) {
        return String(s && (s.seriesId || 'main')) !== sid;
    });
}

function _tvIndicatorDependsOnSeries(info, seriesId) {
    if (!info) return false;
    var sid = seriesId || 'main';
    var primary = info.sourceSeriesId || 'main';
    if (String(primary) === String(sid)) return true;
    if (info.secondarySeriesId && String(info.secondarySeriesId) === String(sid)) return true;
    return false;
}

function _tvRecomputeIndicatorSeries(chartId, seriesId, recomputedGroups) {
    var info = _activeIndicators[seriesId];
    if (!info || info.chartId !== chartId) return;
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry) return;
    var type = info.type || info.name;
    var baseName = (info.name || '').replace(/\s*\(\d+\)\s*$/, '');
    var rawData = _tvSeriesRawData(entry, info.sourceSeriesId || 'main');
    if (!rawData || !rawData.length) return;

    var period = Math.max(1, _tvToNumber(info.period, 14));
    var multiplier = _tvToNumber(info.multiplier, 2);

    if (type === 'moving-average-ex') {
        var maSource = info.source || 'close';
        var maMethod = info.method || 'SMA';
        var maBase = rawData.map(function(p) { return { time: p.time, value: _tvIndicatorValue(p, maSource) }; });
        var maFn = maMethod === 'EMA' ? _computeEMA : (maMethod === 'WMA' ? _computeWMA : _computeSMA);
        var maVals = maFn(maBase, period, 'value');
        var maSeries = entry.seriesMap[seriesId];
        if (maSeries) maSeries.setData(maVals.filter(function(v) { return v.value !== undefined; }));
        return;
    }

    if (type === 'momentum') {
        var momSource = info.source || 'close';
        var momSeries = entry.seriesMap[seriesId];
        if (momSeries) momSeries.setData(_tvComputeMomentum(rawData, period, momSource).filter(function(v) { return v.value !== undefined; }));
        return;
    }

    if (type === 'percent-change') {
        var pcSource = info.source || 'close';
        var pcSeries = entry.seriesMap[seriesId];
        if (pcSeries) pcSeries.setData(_tvComputePercentChange(rawData, pcSource).filter(function(v) { return v.value !== undefined; }));
        return;
    }

    if (type === 'correlation') {
        var secData = _tvSeriesRawData(entry, info.secondarySeriesId);
        var cSeries = entry.seriesMap[seriesId];
        var psrc = info.primarySource || 'close';
        var ssrc = info.secondarySource || 'close';
        if (cSeries) cSeries.setData(_tvComputeCorrelation(rawData, secData, Math.max(2, period), psrc, ssrc).filter(function(v) { return v.value !== undefined; }));
        return;
    }

    if (type === 'spread' || type === 'ratio' || type === 'sum' || type === 'product') {
        var secData2 = _tvSeriesRawData(entry, info.secondarySeriesId);
        var biSeries = entry.seriesMap[seriesId];
        var psrc2 = info.primarySource || 'close';
        var ssrc2 = info.secondarySource || 'close';
        if (biSeries) biSeries.setData(_tvComputeBinary(rawData, secData2, psrc2, ssrc2, type).filter(function(v) { return v.value !== undefined; }));
        return;
    }

    if (type === 'average-price') {
        var apSeries = entry.seriesMap[seriesId];
        if (apSeries) apSeries.setData(_tvComputeAveragePrice(rawData).filter(function(v) { return v.value !== undefined; }));
        return;
    }

    if (type === 'median-price') {
        var mpSeries = entry.seriesMap[seriesId];
        if (mpSeries) mpSeries.setData(_tvComputeMedianPrice(rawData).filter(function(v) { return v.value !== undefined; }));
        return;
    }

    if (type === 'weighted-close') {
        var wcSeries = entry.seriesMap[seriesId];
        if (wcSeries) wcSeries.setData(_tvComputeWeightedClose(rawData).filter(function(v) { return v.value !== undefined; }));
        return;
    }

    if (baseName === 'SMA' || baseName === 'EMA' || baseName === 'WMA') {
        var fn2 = baseName === 'SMA' ? _computeSMA : baseName === 'EMA' ? _computeEMA : _computeWMA;
        var s2 = entry.seriesMap[seriesId];
        if (s2) s2.setData(fn2(rawData, period).filter(function(v) { return v.value !== undefined; }));
        return;
    }

    if (info.group && type === 'bollinger-bands') {
        if (recomputedGroups && recomputedGroups[info.group]) return;
        if (recomputedGroups) recomputedGroups[info.group] = true;
        var bb2 = _computeBollingerBands(rawData, period, multiplier);
        var gKeys = Object.keys(_activeIndicators);
        for (var gi = 0; gi < gKeys.length; gi++) {
            var gInfo = _activeIndicators[gKeys[gi]];
            if (!gInfo || gInfo.group !== info.group || gInfo.chartId !== chartId) continue;
            var gs2 = entry.seriesMap[gKeys[gi]];
            var bbD = gKeys[gi].indexOf('upper') >= 0 ? bb2.upper : gKeys[gi].indexOf('lower') >= 0 ? bb2.lower : bb2.middle;
            if (gs2) gs2.setData(bbD.filter(function(v) { return v.value !== undefined; }));
        }
        return;
    }

    if (info.name === 'RSI') {
        var rsN = entry.seriesMap[seriesId];
        if (rsN) rsN.setData(_computeRSI(rawData, period).filter(function(v) { return v.value !== undefined; }));
        return;
    }

    if (info.name === 'ATR') {
        var atN = entry.seriesMap[seriesId];
        if (atN) atN.setData(_computeATR(rawData, period).filter(function(v) { return v.value !== undefined; }));
        return;
    }

    if (info.name === 'Volume SMA') {
        var vN = entry.seriesMap[seriesId];
        if (vN) vN.setData(_computeSMA(rawData, period, 'volume').filter(function(v) { return v.value !== undefined; }));
    }
}

function _tvRecomputeIndicatorsForChart(chartId, changedSeriesId) {
    var entry = window.__PYWRY_TVCHARTS__ && window.__PYWRY_TVCHARTS__[chartId];
    if (!entry) return;
    var ids = Object.keys(_activeIndicators);
    var groupsDone = {};
    for (var i = 0; i < ids.length; i++) {
        var sid = ids[i];
        var info = _activeIndicators[sid];
        if (!info || info.chartId !== chartId) continue;
        if (changedSeriesId && !_tvIndicatorDependsOnSeries(info, changedSeriesId)) continue;
        _tvRecomputeIndicatorSeries(chartId, sid, groupsDone);
    }
    _tvRebuildIndicatorLegend(chartId);
}

function _tvBuildIntervalRequestContext(chartId, interval) {
    var resolved = _tvResolveChartEntry(chartId || 'main');
    var entry = resolved ? resolved.entry : null;
    var effectiveChartId = resolved ? resolved.chartId : (chartId || 'main');
    var seriesIds = entry && entry.seriesMap ? Object.keys(entry.seriesMap) : [];
    var compareSeriesIds = [];
    for (var i = 0; i < seriesIds.length; i++) {
        var sid = seriesIds[i];
        if (sid === 'main') continue;
        if (_activeIndicators[sid]) continue;
        compareSeriesIds.push(sid);
    }

    var indicators = [];
    var aiKeys = Object.keys(_activeIndicators);
    for (var j = 0; j < aiKeys.length; j++) {
        var indId = aiKeys[j];
        var ind = _activeIndicators[indId];
        if (!ind || ind.chartId !== effectiveChartId) continue;
        indicators.push({
            seriesId: indId,
            type: ind.type || ind.name,
            period: ind.period,
            multiplier: ind.multiplier,
            sourceSeriesId: ind.sourceSeriesId || 'main',
            secondarySeriesId: ind.secondarySeriesId || null,
            source: ind.source || null,
            method: ind.method || null,
            primarySource: ind.primarySource || null,
            secondarySource: ind.secondarySource || null,
        });
    }

    var mainSymbol = '';
    if (entry && entry.payload) {
        // Prefer the actual symbol from the series descriptor or resolved info
        if (entry.payload.series && Array.isArray(entry.payload.series) && entry.payload.series[0] && entry.payload.series[0].symbol) {
            mainSymbol = String(entry.payload.series[0].symbol);
        } else if (entry._resolvedSymbolInfo && entry._resolvedSymbolInfo.main && entry._resolvedSymbolInfo.main.symbol) {
            mainSymbol = String(entry._resolvedSymbolInfo.main.symbol);
        } else if (entry.payload.title) {
            mainSymbol = String(entry.payload.title);
        }
    }
    var mainPeriodParams = _tvBuildPeriodParams(entry, 'main');
    mainPeriodParams.firstDataRequest = _tvMarkFirstDataRequest(entry, 'main');

    return {
        chartId: effectiveChartId,
        symbol: mainSymbol,
        symbolInfo: null,
        seriesId: 'main',
        interval: interval,
        resolution: interval,
        periodParams: mainPeriodParams,
        seriesIds: seriesIds,
        compareSeriesIds: compareSeriesIds,
        indicators: indicators,
    };
}

function _tvDisplayLabelFromSymbolInfo(info, fallbackSymbol) {
    if (info && typeof info === 'object') {
        var display = String(info.displaySymbol || info.ticker || '').trim();
        if (display) return display.toUpperCase();
        var full = String(info.fullName || '').trim();
        if (full) return full;
        var symbolFromInfo = String(info.symbol || '').trim();
        if (symbolFromInfo) {
            return symbolFromInfo.indexOf(':') >= 0
                ? symbolFromInfo.split(':').pop().trim().toUpperCase()
                : symbolFromInfo.toUpperCase();
        }
    }
    var raw = String(fallbackSymbol || '').trim();
    if (!raw) return '';
    return raw.indexOf(':') >= 0 ? raw.split(':').pop().trim().toUpperCase() : raw.toUpperCase();
}

function _tvBuildPeriodParams(entry, seriesId) {
    var bars = [];
    if (entry && entry._seriesRawData && entry._seriesRawData[seriesId] && entry._seriesRawData[seriesId].length) {
        bars = entry._seriesRawData[seriesId];
    } else if (entry && entry._seriesRawData && entry._seriesRawData.main && entry._seriesRawData.main.length) {
        bars = entry._seriesRawData.main;
    } else if (entry && entry._rawData && entry._rawData.length) {
        bars = entry._rawData;
    }

    var countBack = bars.length || 300;
    var from = 0;
    var to = 0;
    if (bars.length) {
        from = _tvTimeToSec(bars[0].time);
        var lastSec = _tvTimeToSec(bars[bars.length - 1].time);
        var stepSec = 60;
        if (bars.length > 1) {
            var prevSec = _tvTimeToSec(bars[bars.length - 2].time);
            stepSec = Math.max(1, lastSec - prevSec);
        }
        to = lastSec + stepSec;
    }

    return {
        from: from,
        to: to,
        countBack: countBack,
    };
}

function _tvMarkFirstDataRequest(entry, seriesId) {
    if (!entry) return false;
    if (!entry._dataRequestSeen) entry._dataRequestSeen = {};
    var first = !entry._dataRequestSeen[seriesId];
    entry._dataRequestSeen[seriesId] = true;
    return first;
}

function _tvEmitIntervalDataRequests(chartId, interval) {
    var ctx = _tvBuildIntervalRequestContext(chartId, interval);
    window.pywry.emit('tvchart:data-request', ctx);
    var resolved = _tvResolveChartEntry(ctx.chartId);
    var entry = resolved ? resolved.entry : null;
    if (!entry || !entry._compareSymbols) return;
    var compareIds = Object.keys(entry._compareSymbols);
    for (var i = 0; i < compareIds.length; i++) {
        var sid = compareIds[i];
        var sym = entry._compareSymbols[sid];
        if (!sym) continue;
        var comparePeriodParams = _tvBuildPeriodParams(entry, sid);
        comparePeriodParams.firstDataRequest = _tvMarkFirstDataRequest(entry, sid);
        window.pywry.emit('tvchart:data-request', {
            chartId: ctx.chartId,
            symbol: sym,
            symbolInfo: entry._compareSymbolInfo && entry._compareSymbolInfo[sid] ? entry._compareSymbolInfo[sid] : null,
            seriesId: sid,
            interval: interval,
            resolution: interval,
            periodParams: comparePeriodParams,
            session: ctx.session,
            timezone: ctx.timezone,
        });
    }
}

function _tvIntervalShortLabel(interval) {
    var labels = {
        '1m':'1m','3m':'3m','5m':'5m','15m':'15m','30m':'30m','45m':'45m',
        '1h':'1H','2h':'2H','3h':'3H','4h':'4H',
        '1d':'D','2d':'2D','3d':'3D',
        '1w':'W','2w':'2W','3w':'3W',
        '1M':'M','2M':'2M','3M':'3M','6M':'6M','12M':'12M'
    };
    return labels[interval] || interval;
}

function _tvTimeToMs(timeValue) {
    if (typeof timeValue === 'number' && isFinite(timeValue)) {
        return timeValue > 1000000000000 ? timeValue : timeValue * 1000;
    }
    if (timeValue && typeof timeValue === 'object' && timeValue.year && timeValue.month && timeValue.day) {
        return Date.UTC(timeValue.year, timeValue.month - 1, timeValue.day);
    }
    var parsed = Date.parse(String(timeValue));
    return isFinite(parsed) ? parsed : NaN;
}

function _tvResolveRangeSpanDays(rangeValue) {
    var spans = {
        '1d': 1,
        '5d': 5,
        '1m': 30,
        '3m': 91,
        '6m': 182,
        '1y': 365,
        '3y': 365 * 3,
        '5y': 365 * 5,
        '10y': 365 * 10,
        '20y': 365 * 20,
    };
    return spans[rangeValue] || spans['1y'];
}

/**
 * Return the number of seconds one bar represents for a given interval string.
 */
function _tvIntervalToSeconds(interval) {
    var m = String(interval || '1d').match(/^(\d+)?([smhdwM])$/i);
    if (!m) return 86400; // default daily
    var n = parseInt(m[1] || '1', 10) || 1;
    var unit = m[2];
    switch (unit) {
        case 's': return n;
        case 'm': return n * 60;
        case 'h': return n * 3600;
        case 'd':
        case 'D': return n * 86400;
        case 'w':
        case 'W': return n * 7 * 86400;
        case 'M': return n * 30 * 86400;
        default:  return 86400;
    }
}

function _tvCurrentInterval(chartId) {
    var btn = _tvScopedById(chartId, 'tvchart-interval-btn');
    if (btn) {
        var selected = btn.getAttribute('data-selected');
        if (selected) return String(selected);
    }
    var entry = window.__PYWRY_TVCHARTS__ && window.__PYWRY_TVCHARTS__[chartId || 'main'];
    if (entry && entry.payload && entry.payload.interval) {
        return String(entry.payload.interval);
    }
    return '1d';
}

function _tvSetIntervalUi(chartId, interval) {
    var label = _tvScopedById(chartId, 'tvchart-interval-label');
    if (label) label.textContent = _tvIntervalShortLabel(interval);
    var btn = _tvScopedById(chartId, 'tvchart-interval-btn');
    if (btn) btn.setAttribute('data-selected', interval);
    var menu = _tvScopedById(chartId, 'tvchart-interval-menu');
    if (menu) {
        menu.querySelectorAll('.tvchart-interval-item').forEach(function(el) {
            el.classList.toggle('selected', el.getAttribute('data-interval') === interval);
        });
    }
}

function _tvResolvePrimaryBars(entry) {
    if (!entry) return [];

    // Best source: ask the actual chart series for its current data.
    // This is always in sync — includes scrollback, real-time updates, etc.
    var series = _tvResolvePrimarySeries(entry);
    if (series && typeof series.data === 'function') {
        try {
            var seriesData = series.data();
            if (seriesData && seriesData.length) return seriesData;
        } catch (e) {}
    }

    // Resolve the primary series ID — may be 'main' or 'series-0' depending
    // on whether the payload specified an explicit seriesId.
    var primaryId = 'main';
    var payload = entry.payload || {};
    var seriesList = payload.series;
    if (seriesList && Array.isArray(seriesList) && seriesList.length > 0) {
        primaryId = seriesList[0].seriesId || 'series-0';
    }

    // When session filtering is active, return the displayed (filtered) bars
    // so that logical indices match what the chart series actually has.
    if (entry._seriesDisplayData) {
        var displayBars = entry._seriesDisplayData[primaryId] || entry._seriesDisplayData.main;
        if (displayBars && displayBars.length) return displayBars;
    }

    // _seriesRawData fallback
    if (entry._seriesRawData) {
        var rawBars = entry._seriesRawData[primaryId] || entry._seriesRawData.main;
        if (rawBars && rawBars.length) return rawBars;
    }

    if (seriesList && seriesList[0] && seriesList[0].bars && seriesList[0].bars.length) {
        return seriesList[0].bars;
    }
    if (payload.bars && payload.bars.length) return payload.bars;
    return [];
}

function _tvResolvePrimarySeries(entry) {
    if (!entry || !entry.seriesMap) return null;
    // Try 'main' first, then 'series-0', then first key
    if (entry.seriesMap.main) return entry.seriesMap.main;
    if (entry.seriesMap['series-0']) return entry.seriesMap['series-0'];
    var keys = Object.keys(entry.seriesMap);
    return keys.length > 0 ? entry.seriesMap[keys[0]] : null;
}

function _tvApplyTimeRangeSelection(entry, range) {
    if (!entry || !entry.chart) return false;
    var bars = _tvResolvePrimaryBars(entry);
    var totalBars = bars.length;
    if (!totalBars) return false;

    if (range === 'all') {
        entry.chart.timeScale().fitContent();
        return true;
    }

    var lastIndex = totalBars - 1;

    // Get the last bar's timestamp in seconds
    var lastBarSec = _tvTimeToSec(bars[lastIndex].time);
    if (!isFinite(lastBarSec)) {
        entry.chart.timeScale().fitContent();
        return false;
    }

    // Compute the cutoff timestamp: last bar minus the requested range
    var cutoffSec;
    if (range === 'ytd') {
        var lastDate = new Date(lastBarSec * 1000);
        cutoffSec = Math.floor(Date.UTC(lastDate.getUTCFullYear(), 0, 1) / 1000);
    } else {
        var spanDays = _tvResolveRangeSpanDays(range);
        cutoffSec = lastBarSec - (spanDays * 86400);
    }

    // Walk the bars to find the first one at or after the cutoff
    var fromIndex = 0;
    for (var i = 0; i < totalBars; i++) {
        var barSec = _tvTimeToSec(bars[i].time);
        if (isFinite(barSec) && barSec >= cutoffSec) {
            fromIndex = i;
            break;
        }
    }

    if (fromIndex >= lastIndex) {
        entry.chart.timeScale().fitContent();
        return false;
    }

    entry.chart.timeScale().setVisibleLogicalRange({
        from: fromIndex,
        to: lastIndex,
    });
    return true;
}

/**
 * Normalise any time value to seconds.  Accepts unix seconds, unix ms,
 * or {year,month,day} business-day objects.
 */
function _tvTimeToSec(timeValue) {
    if (typeof timeValue === 'number' && isFinite(timeValue)) {
        return timeValue > 1e12 ? Math.floor(timeValue / 1000) : timeValue;
    }
    if (timeValue && typeof timeValue === 'object' && timeValue.year && timeValue.month && timeValue.day) {
        return Math.floor(Date.UTC(timeValue.year, timeValue.month - 1, timeValue.day) / 1000);
    }
    var parsed = Date.parse(String(timeValue));
    return isFinite(parsed) ? Math.floor(parsed / 1000) : NaN;
}

function _tvApplyAbsoluteDateRange(entry, fromSec, toSec, fallbackFit) {
    if (!entry || !entry.chart) return false;
    var bars = _tvResolvePrimaryBars(entry);
    var totalBars = bars.length;
    if (!totalBars) return false;

    // Normalise inputs — callers may pass ms or seconds
    var fromS = fromSec > 1e12 ? Math.floor(fromSec / 1000) : fromSec;
    var toS = toSec > 1e12 ? Math.floor(toSec / 1000) : toSec;

    var fromIndex = -1;
    var toIndex = -1;
    for (var index = 0; index < totalBars; index++) {
        var barSec = _tvTimeToSec(bars[index].time);
        if (!isFinite(barSec)) continue;
        if (fromIndex === -1 && barSec >= fromS) fromIndex = index;
        if (barSec <= toS) toIndex = index;
    }

    if (fromIndex === -1 || toIndex === -1 || fromIndex > toIndex) {
        if (fallbackFit) entry.chart.timeScale().fitContent();
        return false;
    }

    entry.chart.timeScale().setVisibleLogicalRange({
        from: fromIndex,
        to: toIndex,
    });
    return true;
}

function _tvPromptDateRangeAndApply(entry) {
    if (!entry) return;
    var bars = _tvResolvePrimaryBars(entry);
    if (!bars.length) return;

    var lastSec = _tvTimeToSec(bars[bars.length - 1].time);
    if (!isFinite(lastSec)) return;
    var defaultEnd = new Date(lastSec * 1000).toISOString().slice(0, 10);
    var defaultStart = new Date((lastSec - 90 * 86400) * 1000).toISOString().slice(0, 10);

    var previous = document.querySelector('.tv-date-range-overlay');
    if (previous && previous.parentNode) previous.parentNode.removeChild(previous);

    function toIsoDate(value) {
        var dt = new Date(value);
        return dt.toISOString().slice(0, 10);
    }

    function parseIsoDate(dateValue) {
        var parsed = Date.parse(String(dateValue || '').trim() + 'T00:00:00Z');
        return isFinite(parsed) ? Math.floor(parsed / 1000) : NaN;
    }

    function parseTimeToSec(timeValue) {
        var raw = String(timeValue || '').trim();
        var parts = raw.split(':');
        if (parts.length !== 2) return NaN;
        var hh = Number(parts[0]);
        var mm = Number(parts[1]);
        if (!isFinite(hh) || !isFinite(mm)) return NaN;
        if (hh < 0 || hh > 23 || mm < 0 || mm > 59) return NaN;
        return (hh * 60 + mm) * 60;
    }

    function findNearestBarIndex(targetSec) {
        var nearest = -1;
        var nearestDiff = Infinity;
        for (var i = 0; i < bars.length; i++) {
            var barSec = _tvTimeToSec(bars[i].time);
            if (!isFinite(barSec)) continue;
            var diff = Math.abs(barSec - targetSec);
            if (diff < nearestDiff) {
                nearestDiff = diff;
                nearest = i;
            }
        }
        return nearest;
    }

    function applyGoToDate(targetSec) {
        var index = findNearestBarIndex(targetSec);
        if (index < 0) {
            entry.chart.timeScale().fitContent();
            return;
        }
        var windowBack = 90;
        var windowForward = 40;
        entry.chart.timeScale().setVisibleLogicalRange({
            from: Math.max(0, index - windowBack),
            to: Math.min(bars.length - 1, index + windowForward),
        });
    }

    var overlay = document.createElement('div');
    overlay.className = 'tv-date-range-overlay';

    var panel = document.createElement('div');
    panel.className = 'tv-date-range-panel';
    overlay.appendChild(panel);

    var header = document.createElement('div');
    header.className = 'tv-date-range-header';
    var title = document.createElement('h3');
    title.textContent = 'Go to';
    header.appendChild(title);
    var closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'tv-date-range-close';
    closeBtn.innerHTML = '<svg viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>';
    header.appendChild(closeBtn);
    panel.appendChild(header);

    var tabs = document.createElement('div');
    tabs.className = 'tv-date-range-tabs';
    var tabDate = document.createElement('button');
    tabDate.type = 'button';
    tabDate.className = 'tv-date-range-tab active';
    tabDate.textContent = 'Date';
    var tabCustom = document.createElement('button');
    tabCustom.type = 'button';
    tabCustom.className = 'tv-date-range-tab';
    tabCustom.textContent = 'Custom range';
    tabs.appendChild(tabDate);
    tabs.appendChild(tabCustom);
    panel.appendChild(tabs);

    var body = document.createElement('div');
    body.className = 'tv-date-range-body';
    panel.appendChild(body);

    var datePane = document.createElement('div');
    datePane.className = 'tv-date-range-pane active';
    var customPane = document.createElement('div');
    customPane.className = 'tv-date-range-pane';
    body.appendChild(datePane);
    body.appendChild(customPane);

    var controlRow = document.createElement('div');
    controlRow.className = 'tv-date-range-controls';
    var dateWrap = document.createElement('div');
    dateWrap.className = 'tv-date-range-input-wrap';
    var dateInput = document.createElement('input');
    dateInput.type = 'text';
    dateInput.className = 'tv-date-range-input tv-date-range-input-date';
    dateInput.value = defaultEnd;
    var dateIconBtn = document.createElement('button');
    dateIconBtn.type = 'button';
    dateIconBtn.className = 'tv-date-range-input-icon-btn';
    dateIconBtn.setAttribute('data-tooltip', 'Calendar');
    dateIconBtn.innerHTML = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><rect x="2.3" y="3.2" width="11.4" height="10.2" rx="1.8"/><line x1="2.3" y1="6" x2="13.7" y2="6"/><line x1="5" y1="2" x2="5" y2="4.1"/><line x1="11" y1="2" x2="11" y2="4.1"/></svg>';
    dateIconBtn.addEventListener('click', function() { dateInput.focus(); });
    dateWrap.appendChild(dateInput);
    dateWrap.appendChild(dateIconBtn);

    var timeWrap = document.createElement('div');
    timeWrap.className = 'tv-date-range-input-wrap';
    var timeInput = document.createElement('input');
    timeInput.type = 'text';
    timeInput.className = 'tv-date-range-input tv-date-range-input-time';
    timeInput.value = '00:00';
    var timeIconBtn = document.createElement('button');
    timeIconBtn.type = 'button';
    timeIconBtn.className = 'tv-date-range-input-icon-btn';
    timeIconBtn.setAttribute('data-tooltip', 'Time');
    timeIconBtn.innerHTML = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="5.8"/><line x1="8" y1="8" x2="8" y2="4.6"/><line x1="8" y1="8" x2="10.9" y2="9.4"/></svg>';
    timeIconBtn.addEventListener('click', function() { timeInput.focus(); });
    timeWrap.appendChild(timeInput);
    timeWrap.appendChild(timeIconBtn);

    controlRow.appendChild(dateWrap);
    controlRow.appendChild(timeWrap);
    datePane.appendChild(controlRow);

    var nav = document.createElement('div');
    nav.className = 'tv-date-range-month-nav';
    var prevBtn = document.createElement('button');
    prevBtn.type = 'button';
    prevBtn.className = 'tv-date-range-month-btn';
    prevBtn.innerHTML = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="10.5,3.2 5.5,8 10.5,12.8"/></svg>';
    var monthLabel = document.createElement('div');
    monthLabel.className = 'tv-date-range-month-label';
    var monthNameSpan = document.createElement('span');
    monthNameSpan.className = 'tv-date-range-month-name';
    var yearInput = document.createElement('input');
    yearInput.type = 'number';
    yearInput.className = 'tv-date-range-year-input';
    yearInput.min = '1900';
    yearInput.max = '2100';
    monthLabel.appendChild(monthNameSpan);
    monthLabel.appendChild(yearInput);
    var nextBtn = document.createElement('button');
    nextBtn.type = 'button';
    nextBtn.className = 'tv-date-range-month-btn';
    nextBtn.innerHTML = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="5.5,3.2 10.5,8 5.5,12.8"/></svg>';
    nav.appendChild(prevBtn);
    nav.appendChild(monthLabel);
    nav.appendChild(nextBtn);
    body.appendChild(nav);

    var weekHeader = document.createElement('div');
    weekHeader.className = 'tv-date-range-week-header';
    ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'].forEach(function(d) {
        var cell = document.createElement('span');
        cell.textContent = d;
        weekHeader.appendChild(cell);
    });
    body.appendChild(weekHeader);

    var grid = document.createElement('div');
    grid.className = 'tv-date-range-grid';
    body.appendChild(grid);

    var customFields = document.createElement('div');
    customFields.className = 'tv-date-range-custom-fields';

    function _buildDateTimeRow(dateValue, timeValue) {
        var row = document.createElement('div');
        row.className = 'tv-date-range-controls tv-date-range-controls-custom';

        var dWrap = document.createElement('div');
        dWrap.className = 'tv-date-range-input-wrap';
        var dInput = document.createElement('input');
        dInput.type = 'text';
        dInput.className = 'tv-date-range-input tv-date-range-input-date';
        dInput.value = dateValue;
        var dIcon = document.createElement('button');
        dIcon.type = 'button';
        dIcon.className = 'tv-date-range-input-icon-btn';
        dIcon.setAttribute('data-tooltip', 'Calendar');
        dIcon.innerHTML = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><rect x="2.3" y="3.2" width="11.4" height="10.2" rx="1.8"/><line x1="2.3" y1="6" x2="13.7" y2="6"/><line x1="5" y1="2" x2="5" y2="4.1"/><line x1="11" y1="2" x2="11" y2="4.1"/></svg>';
        dIcon.addEventListener('click', function() { dInput.focus(); });
        dWrap.appendChild(dInput);
        dWrap.appendChild(dIcon);

        var tWrap = document.createElement('div');
        tWrap.className = 'tv-date-range-input-wrap';
        var tInput = document.createElement('input');
        tInput.type = 'text';
        tInput.className = 'tv-date-range-input tv-date-range-input-time';
        tInput.value = timeValue;
        var tIcon = document.createElement('button');
        tIcon.type = 'button';
        tIcon.className = 'tv-date-range-input-icon-btn';
        tIcon.setAttribute('data-tooltip', 'Time');
        tIcon.innerHTML = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="5.8"/><line x1="8" y1="8" x2="8" y2="4.6"/><line x1="8" y1="8" x2="10.9" y2="9.4"/></svg>';
        tIcon.addEventListener('click', function() { tInput.focus(); });
        tWrap.appendChild(tInput);
        tWrap.appendChild(tIcon);

        row.appendChild(dWrap);
        row.appendChild(tWrap);
        return { row: row, dateInput: dInput, timeInput: tInput };
    }

    var customStartRow = _buildDateTimeRow(defaultStart, '00:00');
    var customEndRow = _buildDateTimeRow(defaultEnd, '00:00');
    customFields.appendChild(customStartRow.row);
    customFields.appendChild(customEndRow.row);
    customPane.appendChild(customFields);

    var footer = document.createElement('div');
    footer.className = 'tv-date-range-footer';
    var cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'tv-date-range-btn tv-date-range-btn-secondary';
    cancelBtn.textContent = 'Cancel';
    var applyBtn = document.createElement('button');
    applyBtn.type = 'button';
    applyBtn.className = 'tv-date-range-btn tv-date-range-btn-primary';
    applyBtn.textContent = 'Go to';
    footer.appendChild(cancelBtn);
    footer.appendChild(applyBtn);
    panel.appendChild(footer);

    var activeTab = 'date';
    var calendarView = 'day';
    var selectedSec = parseIsoDate(defaultEnd);
    var viewDate = new Date(selectedSec * 1000);
    var customStartSec = parseIsoDate(defaultStart);
    var customEndSec = parseIsoDate(defaultEnd);
    var customSelectPhase = 'start';

    function _syncCustomInputsFromState() {
        if (isFinite(customStartSec)) customStartRow.dateInput.value = toIsoDate(customStartSec * 1000);
        if (isFinite(customEndSec)) customEndRow.dateInput.value = toIsoDate(customEndSec * 1000);
    }

    function _parseDateTime(dateVal, timeVal) {
        var daySec = parseIsoDate(dateVal);
        if (!isFinite(daySec)) return NaN;
        var timeSec = parseTimeToSec(timeVal);
        if (!isFinite(timeSec)) timeSec = 0;
        return daySec + timeSec;
    }

    function _recalcCustomRangeFromInputs() {
        var s = parseIsoDate(customStartRow.dateInput.value);
        var e = parseIsoDate(customEndRow.dateInput.value);
        if (!isFinite(s) || !isFinite(e)) return;
        customStartSec = s;
        customEndSec = e;
        if (customEndSec < customStartSec) {
            var t = customStartSec;
            customStartSec = customEndSec;
            customEndSec = t;
            _syncCustomInputsFromState();
        }
    }

    function setTab(tab) {
        activeTab = tab;
        tabDate.classList.toggle('active', tab === 'date');
        tabCustom.classList.toggle('active', tab === 'custom');
        datePane.classList.toggle('active', tab === 'date');
        customPane.classList.toggle('active', tab === 'custom');
        renderCalendar();
    }

    function renderCalendar() {
        var monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
        var shortMonths = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        grid.innerHTML = '';
        yearInput.value = String(viewDate.getUTCFullYear());

        if (calendarView === 'month') {
            monthNameSpan.textContent = '';
            weekHeader.style.display = 'none';
            grid.className = 'tv-date-range-grid tv-date-range-grid-pick';
            for (var mi = 0; mi < 12; mi++) {
                var mBtn = document.createElement('button');
                mBtn.type = 'button';
                mBtn.className = 'tv-date-range-cell';
                mBtn.textContent = shortMonths[mi];
                if (mi === viewDate.getUTCMonth()) mBtn.classList.add('selected');
                mBtn.addEventListener('click', (function(m) {
                    return function() {
                        viewDate = new Date(Date.UTC(viewDate.getUTCFullYear(), m, 1));
                        calendarView = 'day';
                        renderCalendar();
                    };
                })(mi));
                grid.appendChild(mBtn);
            }
            return;
        }

        /* day view */
        monthNameSpan.textContent = monthNames[viewDate.getUTCMonth()];
        weekHeader.style.display = '';
        grid.className = 'tv-date-range-grid';

        var firstOfMonth = Date.UTC(viewDate.getUTCFullYear(), viewDate.getUTCMonth(), 1);
        var startWeekday = (new Date(firstOfMonth).getUTCDay() + 6) % 7;
        var daysInMonth = new Date(Date.UTC(viewDate.getUTCFullYear(), viewDate.getUTCMonth() + 1, 0)).getUTCDate();
        var prevMonthDays = new Date(Date.UTC(viewDate.getUTCFullYear(), viewDate.getUTCMonth(), 0)).getUTCDate();

        for (var i = 0; i < 42; i++) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'tv-date-range-day';
            var dayNumber;
            var dayMs;
            if (i < startWeekday) {
                dayNumber = prevMonthDays - startWeekday + i + 1;
                dayMs = Date.UTC(viewDate.getUTCFullYear(), viewDate.getUTCMonth() - 1, dayNumber);
                btn.classList.add('muted');
            } else if (i >= startWeekday + daysInMonth) {
                dayNumber = i - startWeekday - daysInMonth + 1;
                dayMs = Date.UTC(viewDate.getUTCFullYear(), viewDate.getUTCMonth() + 1, dayNumber);
                btn.classList.add('muted');
            } else {
                dayNumber = i - startWeekday + 1;
                dayMs = Date.UTC(viewDate.getUTCFullYear(), viewDate.getUTCMonth(), dayNumber);
            }

            btn.textContent = String(dayNumber);
            if (activeTab === 'custom') {
                var dayKey = toIsoDate(dayMs);
                var startKey = isFinite(customStartSec) ? toIsoDate(customStartSec * 1000) : '';
                var endKey = isFinite(customEndSec) ? toIsoDate(customEndSec * 1000) : '';
                var minKey = startKey;
                var maxKey = endKey;
                if (startKey && endKey && startKey > endKey) {
                    minKey = endKey;
                    maxKey = startKey;
                }
                if (minKey && maxKey && dayKey > minKey && dayKey < maxKey) {
                    btn.classList.add('in-range');
                }
                if (dayKey === minKey) btn.classList.add('range-start');
                if (dayKey === maxKey) btn.classList.add('range-end');
            } else if (toIsoDate(dayMs) === toIsoDate(selectedSec * 1000)) {
                btn.classList.add('selected');
            }
            btn.addEventListener('click', function(ms) {
                return function() {
                    var sec = Math.floor(ms / 1000);
                    if (activeTab === 'custom') {
                        if (customSelectPhase === 'start') {
                            customStartSec = sec;
                            if (!isFinite(customEndSec) || customEndSec < customStartSec) customEndSec = customStartSec;
                            customSelectPhase = 'end';
                        } else {
                            customEndSec = sec;
                            if (customEndSec < customStartSec) {
                                var tmp = customStartSec;
                                customStartSec = customEndSec;
                                customEndSec = tmp;
                            }
                            customSelectPhase = 'start';
                        }
                        _syncCustomInputsFromState();
                    } else {
                        selectedSec = sec;
                        dateInput.value = toIsoDate(ms);
                    }
                    viewDate = new Date(ms);
                    renderCalendar();
                };
            }(dayMs));
            grid.appendChild(btn);
        }
    }

    function closeDialog() {
        if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
        document.removeEventListener('keydown', onEsc, true);
    }

    function onEsc(evt) {
        if (evt.key === 'Escape') {
            evt.preventDefault();
            closeDialog();
        }
    }

    function applySelection() {
        if (activeTab === 'custom') {
            var startSec = _parseDateTime(customStartRow.dateInput.value, customStartRow.timeInput.value);
            var endSec = _parseDateTime(customEndRow.dateInput.value, customEndRow.timeInput.value);
            if (!isFinite(startSec) || !isFinite(endSec)) return;
            var fromSec = Math.min(startSec, endSec);
            var toSec = Math.max(startSec, endSec);
            _tvApplyAbsoluteDateRange(entry, fromSec, toSec, true);
            closeDialog();
            return;
        }

        var chosenDateSec = parseIsoDate(dateInput.value);
        if (!isFinite(chosenDateSec)) return;
        var chosenTimeSec = parseTimeToSec(timeInput.value);
        if (!isFinite(chosenTimeSec)) chosenTimeSec = 0;
        applyGoToDate(chosenDateSec + chosenTimeSec);
        closeDialog();
    }

    tabDate.addEventListener('click', function() { setTab('date'); });
    tabCustom.addEventListener('click', function() { setTab('custom'); });
    monthNameSpan.addEventListener('click', function() {
        calendarView = calendarView === 'day' ? 'month' : 'day';
        renderCalendar();
    });
    yearInput.addEventListener('change', function() {
        var y = parseInt(yearInput.value, 10);
        if (!isFinite(y) || y < 1900 || y > 2100) return;
        viewDate = new Date(Date.UTC(y, viewDate.getUTCMonth(), 1));
        renderCalendar();
    });
    yearInput.addEventListener('keydown', function(evt) {
        if (evt.key === 'Enter') {
            evt.preventDefault();
            yearInput.blur();
        }
    });
    prevBtn.addEventListener('click', function() {
        if (calendarView === 'month') {
            viewDate = new Date(Date.UTC(viewDate.getUTCFullYear() - 1, viewDate.getUTCMonth(), 1));
        } else {
            viewDate = new Date(Date.UTC(viewDate.getUTCFullYear(), viewDate.getUTCMonth() - 1, 1));
        }
        renderCalendar();
    });
    nextBtn.addEventListener('click', function() {
        if (calendarView === 'month') {
            viewDate = new Date(Date.UTC(viewDate.getUTCFullYear() + 1, viewDate.getUTCMonth(), 1));
        } else {
            viewDate = new Date(Date.UTC(viewDate.getUTCFullYear(), viewDate.getUTCMonth() + 1, 1));
        }
        renderCalendar();
    });
    dateInput.addEventListener('change', function() {
        var parsed = parseIsoDate(dateInput.value);
        if (!isFinite(parsed)) return;
        selectedSec = parsed;
        viewDate = new Date(parsed * 1000);
        renderCalendar();
    });
    dateInput.addEventListener('input', function() {
        var parsed = parseIsoDate(dateInput.value);
        if (!isFinite(parsed)) return;
        selectedSec = parsed;
        viewDate = new Date(parsed * 1000);
        renderCalendar();
    });
    dateInput.addEventListener('keydown', function(evt) {
        if (evt.key === 'Enter') {
            evt.preventDefault();
            applySelection();
        }
    });
    timeInput.addEventListener('keydown', function(evt) {
        if (evt.key === 'Enter') {
            evt.preventDefault();
            applySelection();
        }
    });
    customStartRow.dateInput.addEventListener('change', function() { _recalcCustomRangeFromInputs(); renderCalendar(); });
    customEndRow.dateInput.addEventListener('change', function() { _recalcCustomRangeFromInputs(); renderCalendar(); });
    customStartRow.timeInput.addEventListener('change', function() { _recalcCustomRangeFromInputs(); renderCalendar(); });
    customEndRow.timeInput.addEventListener('change', function() { _recalcCustomRangeFromInputs(); renderCalendar(); });

    overlay.addEventListener('click', function(evt) {
        if (evt.target === overlay) closeDialog();
    });
    closeBtn.addEventListener('click', closeDialog);
    cancelBtn.addEventListener('click', closeDialog);
    applyBtn.addEventListener('click', applySelection);
    document.addEventListener('keydown', onEsc, true);

    renderCalendar();
    setTab('date');
    _tvAppendOverlay(entry.chartId, overlay);
    dateInput.focus();
}

function _tvSeriesRawData(entry, seriesId) {
    if (entry._seriesRawData && entry._seriesRawData[seriesId]) return entry._seriesRawData[seriesId];
    if (seriesId === 'main' && entry._rawData) return entry._rawData;
    var s = entry.seriesMap[seriesId];
    if (s && typeof s.data === 'function') {
        try { return s.data() || []; } catch (e) {}
    }
    return [];
}

function _tvResolveScalePlacement(entry) {
    var prefs = entry && entry._chartPrefs ? entry._chartPrefs : null;
    var placement = prefs && prefs.scalesPlacement ? prefs.scalesPlacement : 'Auto';
    return placement === 'Left' ? 'left' : 'right';
}

function _tvCrosshairLinesVisible(entry) {
    var prefs = entry && entry._chartPrefs ? entry._chartPrefs : {};
    return prefs.crosshairEnabled === true;
}

function _tvApplyHoverReadoutMode(entry) {
    if (!entry || !entry.chart || typeof entry.chart.applyOptions !== 'function') return;

    var prefs = entry._chartPrefs || {};
    var settings = prefs.settings || {};
    var linesVisible = _tvCrosshairLinesVisible(entry);
    var crosshairColor = prefs.crosshairColor || _cssVar('--pywry-tvchart-crosshair-color');
    var lineColor = linesVisible ? crosshairColor : 'rgba(0, 0, 0, 0)';
    var lineStyle = _tvLineStyleFromName(settings['Line style']);
    var lineWidth = _tvClamp(_tvToNumber(settings['Line width'], 1), 1, 4);

    try {
        entry.chart.applyOptions({
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: {
                    color: lineColor || undefined,
                    visible: linesVisible,
                    labelVisible: true,
                    style: lineStyle,
                    width: lineWidth,
                },
                horzLine: {
                    color: lineColor || undefined,
                    visible: linesVisible,
                    labelVisible: linesVisible,
                    style: lineStyle,
                    width: lineWidth,
                },
            },
        });
    } catch (e) {}
}

function _tvRegisterCustomPriceScaleId(entry, scaleId) {
    if (!entry || !scaleId || scaleId === 'left' || scaleId === 'right') return;
    if (!entry._customPriceScaleIds) entry._customPriceScaleIds = {};
    entry._customPriceScaleIds[scaleId] = true;
}

function _tvReserveComparePane(entry, seriesId) {
    if (!entry) return 1;
    if (!entry._comparePaneBySeries) entry._comparePaneBySeries = {};
    var sid = seriesId || ('compare-pane-' + Date.now());
    if (entry._comparePaneBySeries[sid] !== undefined) {
        return entry._comparePaneBySeries[sid];
    }
    var startPane = entry.volumeMap && entry.volumeMap.main ? 2 : 1;
    if (!entry._nextPane || entry._nextPane < startPane) entry._nextPane = startPane;
    var paneIndex = entry._nextPane;
    entry._nextPane += 1;
    entry._comparePaneBySeries[sid] = paneIndex;
    return paneIndex;
}

function _tvApplyCustomScaleSide(entry, side, options) {
    if (!entry || !entry.chart || !entry._customPriceScaleIds) return;
    var scaleIds = Object.keys(entry._customPriceScaleIds);
    for (var i = 0; i < scaleIds.length; i++) {
        var scaleId = scaleIds[i];
        try {
            entry.chart.priceScale(scaleId).applyOptions(_tvMerge({
                visible: true,
                position: side,
            }, options || {}));
        } catch (e) {}
    }
}

function _tvCreateIndicatorLine(entry, color, lineWidth, isSubplot, useBaseline) {
    var paneIndex = 0;
    var series;
    var seriesCtor = useBaseline ? LightweightCharts.BaselineSeries : LightweightCharts.LineSeries;
    var baseOpts;
    if (useBaseline) {
        baseOpts = {
            baseValue: { type: 'price', price: 0 },
            topLineColor: color,
            bottomLineColor: color,
            topFillColor1: 'rgba(76, 175, 80, 0.28)',
            topFillColor2: 'rgba(76, 175, 80, 0.05)',
            bottomFillColor1: 'rgba(239, 83, 80, 0.05)',
            bottomFillColor2: 'rgba(239, 83, 80, 0.28)',
            lineWidth: lineWidth || 2,
            lastValueVisible: true,
            priceLineVisible: false,
        };
    } else {
        baseOpts = { color: color, lineWidth: lineWidth || 2, lastValueVisible: true, priceLineVisible: false };
    }
    if (isSubplot) {
        if (!entry._nextPane) entry._nextPane = 1;
        paneIndex = entry._nextPane;
        try {
            series = entry.chart.addSeries(seriesCtor, baseOpts, paneIndex);
            entry._nextPane++;
        } catch (e) {
            try {
                var legacyMethod = useBaseline ? 'addBaselineSeries' : 'addLineSeries';
                if (typeof entry.chart[legacyMethod] === 'function') {
                    series = entry.chart[legacyMethod](baseOpts, paneIndex);
                    entry._nextPane++;
                }
            } catch (e2) {}

            if (!series) {
                // Do not silently fall back to shared main-pane axes for subplot indicators.
                throw new Error('[pywry:tvchart] Unable to create independent subplot pane for indicator');
            }
        }
    }
    if (!series) {
        var mainScaleId = _tvResolveScalePlacement(entry);
        var mainOpts;
        if (useBaseline) {
            mainOpts = _tvMerge(baseOpts, { priceScaleId: mainScaleId, lastValueVisible: false });
        } else {
            mainOpts = { color: color, lineWidth: lineWidth || 2, priceScaleId: mainScaleId, lastValueVisible: false, priceLineVisible: false };
        }
        series = entry.chart.addSeries(seriesCtor, mainOpts);
    }
    return { series: series, paneIndex: paneIndex, isSubplot: paneIndex > 0 };
}

function _tvAddIndicator(indicatorDef, chartId) {
    chartId = chartId || 'main';
    var entry = window.__PYWRY_TVCHARTS__[chartId];
        if (!entry || !entry.chart || !entry.chartId) return;

    // Snapshot active indicator keys before add (for undo tracking)
    var _preKeys = Object.keys(_activeIndicators).slice();

    var srcIds = _tvIndicatorSourceSeriesIds(entry);
    if (!srcIds.length) return;

    var primarySeriesId = srcIds[0];
    var secondarySeriesId = srcIds.length > 1 ? srcIds[1] : null;
    var rawData = _tvSeriesRawData(entry, primarySeriesId);
    if (!rawData || rawData.length === 0) return;

    var name = indicatorDef.name;
    var key = indicatorDef.key || (indicatorDef.name || '').toLowerCase().replace(/\s+/g, '-');
    var period = Number(indicatorDef.defaultPeriod || 0);
    var color = indicatorDef._color || _getNextIndicatorColor();
    var baseName = name.replace(/\s*\(\d+\)\s*$/, '');

    function createAndSetLine(data, lw, sub, useBaseline) {
        var created = _tvCreateIndicatorLine(entry, color, lw || 2, !!sub, !!useBaseline);
        created.series.setData(data.filter(function(v) { return v.value !== undefined && isFinite(v.value); }));
        return created;
    }

    function addSingleSeriesIndicator(idPrefix, data, meta, lw, sub, useBaseline) {
        var sid = 'ind_' + idPrefix + '_' + Date.now();
        var created = createAndSetLine(data, lw || 2, sub, useBaseline);
        entry.seriesMap[sid] = created.series;
        _activeIndicators[sid] = _tvMerge({
            name: name,
            period: period,
            chartId: chartId,
            color: color,
            paneIndex: created.paneIndex,
            isSubplot: created.isSubplot,
            type: key,
            sourceSeriesId: primarySeriesId,
            secondarySeriesId: secondarySeriesId,
        }, meta || {});
        return sid;
    }

    if (indicatorDef.requiresSecondary && !secondarySeriesId) {
        _tvHideIndicatorsPanel();
        _tvShowIndicatorSymbolPicker(chartId, indicatorDef);
        return;
    }

    // ========== LIGHTWEIGHT EXAMPLES ==========
    if (key === 'average-price') {
        addSingleSeriesIndicator('avg_price', _tvComputeAveragePrice(rawData), { period: 0 }, 2, false);
    } else if (key === 'median-price') {
        addSingleSeriesIndicator('median_price', _tvComputeMedianPrice(rawData), { period: 0 }, 2, false);
    } else if (key === 'weighted-close') {
        addSingleSeriesIndicator('weighted_close', _tvComputeWeightedClose(rawData), { period: 0 }, 2, false);
    } else if (key === 'momentum') {
        var momLength = Math.max(1, period || 10);
        addSingleSeriesIndicator('momentum', _tvComputeMomentum(rawData, momLength, indicatorDef._source || 'close'), {
            period: momLength,
            source: indicatorDef._source || 'close',
        }, 2, true);
    } else if (key === 'moving-average-ex') {
        var maLength = Math.max(1, period || 10);
        var maSource = indicatorDef._source || 'close';
        var maMethod = indicatorDef._method || 'SMA';
        var maBase = rawData.map(function(p) { return { time: p.time, value: _tvIndicatorValue(p, maSource) }; });
        var maFn = maMethod === 'EMA' ? _computeEMA : (maMethod === 'WMA' ? _computeWMA : _computeSMA);
        var maVals = maFn(maBase, maLength, 'value');
        addSingleSeriesIndicator('moving_avg_ex', maVals, {
            period: maLength,
            method: maMethod,
            source: maSource,
        }, 2, false);
    } else if (key === 'percent-change') {
        addSingleSeriesIndicator('pct_change', _tvComputePercentChange(rawData, indicatorDef._source || 'close'), {
            period: 0,
            source: indicatorDef._source || 'close',
        }, 2, true);
    } else if (key === 'spread') {
        var secData = _tvSeriesRawData(entry, secondarySeriesId);
        addSingleSeriesIndicator('spread', _tvComputeBinary(rawData, secData, indicatorDef._primarySource || 'close', indicatorDef._secondarySource || 'close', 'spread'), {
            period: 0,
            primarySource: indicatorDef._primarySource || 'close',
            secondarySource: indicatorDef._secondarySource || 'close',
            secondarySeriesId: secondarySeriesId,
            isBaseline: true,
        }, 2, true, true);
    } else if (key === 'ratio') {
        var secData = _tvSeriesRawData(entry, secondarySeriesId);
        addSingleSeriesIndicator('ratio', _tvComputeBinary(rawData, secData, indicatorDef._primarySource || 'close', indicatorDef._secondarySource || 'close', 'ratio'), {
            period: 0,
            primarySource: indicatorDef._primarySource || 'close',
            secondarySource: indicatorDef._secondarySource || 'close',
            secondarySeriesId: secondarySeriesId,
            isBaseline: true,
        }, 2, true, true);
    } else if (key === 'sum') {
        var secData = _tvSeriesRawData(entry, secondarySeriesId);
        addSingleSeriesIndicator('sum', _tvComputeBinary(rawData, secData, indicatorDef._primarySource || 'close', indicatorDef._secondarySource || 'close', 'sum'), {
            period: 0,
            primarySource: indicatorDef._primarySource || 'close',
            secondarySource: indicatorDef._secondarySource || 'close',
            secondarySeriesId: secondarySeriesId,
            isBaseline: true,
        }, 2, true, true);
    } else if (key === 'product') {
        var secData = _tvSeriesRawData(entry, secondarySeriesId);
        addSingleSeriesIndicator('product', _tvComputeBinary(rawData, secData, indicatorDef._primarySource || 'close', indicatorDef._secondarySource || 'close', 'product'), {
            period: 0,
            primarySource: indicatorDef._primarySource || 'close',
            secondarySource: indicatorDef._secondarySource || 'close',
            secondarySeriesId: secondarySeriesId,
            isBaseline: true,
        }, 2, true, true);
    } else if (key === 'correlation') {
        var corrLen = Math.max(2, period || 20);
        var secData2 = _tvSeriesRawData(entry, secondarySeriesId);
        addSingleSeriesIndicator('correlation', _tvComputeCorrelation(rawData, secData2, corrLen, indicatorDef._primarySource || 'close', indicatorDef._secondarySource || 'close'), {
            period: corrLen,
            primarySource: indicatorDef._primarySource || 'close',
            secondarySource: indicatorDef._secondarySource || 'close',
            secondarySeriesId: secondarySeriesId,
            isBaseline: true,
        }, 2, true, true);

    // ========== MOVING AVERAGES ==========
    } else if (name === 'SMA' || name === 'EMA' || name === 'WMA') {
        var maFn = name === 'SMA' ? _computeSMA : name === 'EMA' ? _computeEMA : _computeWMA;
        var maPeriod = period || 20;
        addSingleSeriesIndicator(name.replace(/\s/g, '_').toLowerCase(), maFn(rawData, maPeriod), { 
            type: name.toLowerCase(), 
            period: maPeriod 
        }, 2, false);
    } else if (name === 'SMA (50)') {
        addSingleSeriesIndicator('sma_50', _computeSMA(rawData, 50), { type: 'sma', period: 50 }, 2, false);
    } else if (name === 'SMA (200)') {
        addSingleSeriesIndicator('sma_200', _computeSMA(rawData, 200), { type: 'sma', period: 200 }, 2, false);
    } else if (name === 'EMA (12)') {
        addSingleSeriesIndicator('ema_12', _computeEMA(rawData, 12), { type: 'ema', period: 12 }, 2, false);
    } else if (name === 'EMA (26)') {
        addSingleSeriesIndicator('ema_26', _computeEMA(rawData, 26), { type: 'ema', period: 26 }, 2, false);

    // ========== VOLATILITY ==========
    } else if (name === 'Bollinger Bands') {
        var bbPeriod = period || 20;
        var bbMult = indicatorDef._multiplier || 2;
        var bbMaType = indicatorDef._maType || 'SMA';
        var bbOffset = indicatorDef._offset || 0;
        var bbSource = indicatorDef._source || 'close';
        var bbBase = rawData.map(function(p) { return { time: p.time, close: _tvIndicatorValue(p, bbSource) }; });
        var bb = _computeBollingerBands(bbBase, bbPeriod, bbMult, bbMaType, bbOffset);
        var sid1 = 'ind_bb_mid_' + Date.now();
        var sid2 = 'ind_bb_upper_' + Date.now();
        var sid3 = 'ind_bb_lower_' + Date.now();
        var bbMidColor = '#ff9800';
        var bbBandColor = '#2196f3';
        var bbScaleId = _tvResolveScalePlacement(entry);
        var s1 = entry.chart.addSeries(LightweightCharts.LineSeries, { color: bbMidColor, lineWidth: 1, priceScaleId: bbScaleId, lastValueVisible: false, priceLineVisible: false });
        var s2 = entry.chart.addSeries(LightweightCharts.LineSeries, { color: bbBandColor, lineWidth: 1, priceScaleId: bbScaleId, lastValueVisible: false, priceLineVisible: false });
        var s3 = entry.chart.addSeries(LightweightCharts.LineSeries, { color: bbBandColor, lineWidth: 1, priceScaleId: bbScaleId, lastValueVisible: false, priceLineVisible: false });
        s1.setData(bb.middle.filter(function(v) { return v.value !== undefined; }));
        s2.setData(bb.upper.filter(function(v) { return v.value !== undefined; }));
        s3.setData(bb.lower.filter(function(v) { return v.value !== undefined; }));
        entry.seriesMap[sid1] = s1; entry.seriesMap[sid2] = s2; entry.seriesMap[sid3] = s3;
        var bbGroup = 'bb_' + Date.now();
        var bbCommon = { period: bbPeriod, chartId: chartId, group: bbGroup, paneIndex: 0, isSubplot: false, multiplier: bbMult, maType: bbMaType, offset: bbOffset, source: bbSource, type: 'bollinger-bands', sourceSeriesId: primarySeriesId, showBandFill: true, bandFillColor: '#2196f3', precision: 'default', labelsOnPriceScale: true, valuesInStatusLine: true, inputsInStatusLine: true };
        _activeIndicators[sid1] = _tvMerge(bbCommon, { name: 'BB Basis', color: bbMidColor });
        _activeIndicators[sid2] = _tvMerge(bbCommon, { name: 'BB Upper', color: bbBandColor });
        _activeIndicators[sid3] = _tvMerge(bbCommon, { name: 'BB Lower', color: bbBandColor });

        // Initialize band fill primitive (rendered via LWC series primitive API)
        _tvEnsureBBFillPrimitive(chartId);

    // ========== MOMENTUM ==========
    } else if (name === 'RSI') {
        var rsiPeriod = period || 14;
        var rsiData = _computeRSI(rawData, rsiPeriod);
        addSingleSeriesIndicator('rsi', rsiData, { type: 'rsi', period: rsiPeriod }, 2, true);

    // ========== VOLATILITY ==========
    } else if (name === 'ATR') {
        var atrPeriod = period || 14;
        var atrRaw = _computeATR(rawData, atrPeriod);
        addSingleSeriesIndicator('atr', atrRaw, { type: 'atr', period: atrPeriod }, 2, true);

    // ========== VOLUME ==========
    } else if (name === 'VWAP') {
        var vwapData = _computeVWAP(rawData);
        addSingleSeriesIndicator('vwap', vwapData, { type: 'vwap', period: 0 }, 2, false);
    } else if (name === 'Volume SMA') {
        var volSmaPeriod = period || 20;
        var volSmaData = _computeSMA(rawData, volSmaPeriod, 'volume');
        addSingleSeriesIndicator('volsma', volSmaData, { type: 'volume-sma', period: volSmaPeriod }, 1, false);
    } else {
        console.error('[pywry:tvchart] Unknown indicator:', name, 'key:', key);
    }

    _tvRebuildIndicatorLegend(chartId);

    // Push undo entry for indicator add (skip during layout restore)
    if (!window.__PYWRY_UNDO_SUPPRESS__) {
        var _postKeys = Object.keys(_activeIndicators);
        var _newSids = [];
        for (var _ui = 0; _ui < _postKeys.length; _ui++) {
            if (_preKeys.indexOf(_postKeys[_ui]) === -1) _newSids.push(_postKeys[_ui]);
        }
        if (_newSids.length > 0) {
            var _undoDef = Object.assign({}, indicatorDef);
            var _undoCid = chartId;
            var _undoSids = _newSids.slice();
            _tvPushUndo({
                label: 'Add ' + (indicatorDef.name || 'indicator'),
                undo: function() {
                    for (var i = 0; i < _undoSids.length; i++) {
                        if (_activeIndicators[_undoSids[i]]) {
                            _tvRemoveIndicator(_undoSids[i]);
                            break;  // _tvRemoveIndicator handles grouped siblings
                        }
                    }
                },
                redo: function() {
                    _tvAddIndicator(_undoDef, _undoCid);
                },
            });
        }
    }
}

/**
 * Apply series colours from theme palette.
 * @param {Object} seriesOptions - User-provided series options
 * @param {string} seriesType - 'Candlestick', 'Line', 'Area', etc.
 * @param {string} theme - 'dark' or 'light'
 * @returns {Object} merged series options
 */
function _tvBuildSeriesOptions(seriesOptions, seriesType, theme) {
    var palette = TVCHART_THEMES._get(theme || 'dark');
    var base = {};

    if (seriesType === 'Candlestick') {
        base = {
            upColor: palette.upColor,
            downColor: palette.downColor,
            grid: palette.grid || {},
            borderUpColor: palette.borderUpColor,
            borderDownColor: palette.borderDownColor,
            wickUpColor: palette.wickUpColor,
            wickDownColor: palette.wickDownColor,
        };
    } else if (seriesType === 'Bar') {
        base = {
            upColor: palette.upColor,
            downColor: palette.downColor,
        };
    } else if (seriesType === 'Line') {
        base = {
            color: palette.upColor,
            lineWidth: 2,
        };
    } else if (seriesType === 'Area') {
        base = {
            topColor: palette.upColor,
            bottomColor: _cssVar('--pywry-tvchart-area-bottom'),
            lineColor: palette.upColor,
            lineWidth: 2,
        };
    } else if (seriesType === 'Baseline') {
        base = {
            topLineColor: palette.upColor,
            topFillColor1: _cssVar('--pywry-tvchart-baseline-top-fill1'),
            topFillColor2: _cssVar('--pywry-tvchart-baseline-top-fill2'),
            bottomLineColor: palette.downColor,
            bottomFillColor1: _cssVar('--pywry-tvchart-baseline-bottom-fill1'),
            bottomFillColor2: _cssVar('--pywry-tvchart-baseline-bottom-fill2'),
        };
    } else if (seriesType === 'Histogram') {
        base = { color: palette.upColor };
    }

    return seriesOptions ? _tvMerge(base, seriesOptions) : base;
}

/**
 * Convert incoming bars to the structure expected by the target series type.
 * Also sorts by time to satisfy Lightweight Charts requirements.
 *
 * @param {Array} bars
 * @param {string} seriesType
 * @returns {Array}
 */
function _tvNormalizeBarsForSeriesType(bars, seriesType) {
    var src = Array.isArray(bars) ? bars : [];
    if (!src.length) return [];

    var wantsValueSeries =
        seriesType === 'Line' ||
        seriesType === 'Area' ||
        seriesType === 'Baseline' ||
        seriesType === 'Histogram';

    var normalized = [];
    for (var i = 0; i < src.length; i++) {
        var b = src[i] || {};
        if (b.time === undefined || b.time === null) continue;

        if (wantsValueSeries) {
            var v = (b.value !== undefined && b.value !== null)
                ? b.value
                : b.close;
            if (v === undefined || v === null || !isFinite(Number(v))) continue;
            normalized.push({ time: b.time, value: Number(v) });
        } else {
            // OHLC-capable series (Candlestick/Bar)
            var o = (b.open !== undefined) ? b.open : b.value;
            var h = (b.high !== undefined) ? b.high : o;
            var l = (b.low !== undefined) ? b.low : o;
            var c = (b.close !== undefined) ? b.close : b.value;
            if ([o, h, l, c].some(function(x) { return x === undefined || x === null || !isFinite(Number(x)); })) {
                continue;
            }
            var normalizedBar = {
                time: b.time,
                open: Number(o),
                high: Number(h),
                low: Number(l),
                close: Number(c),
            };
            if (b.volume !== undefined && b.volume !== null && isFinite(Number(b.volume))) {
                normalizedBar.volume = Number(b.volume);
            }
            normalized.push(normalizedBar);
        }
    }

    normalized.sort(function(a, b) {
        var ta = a.time;
        var tb = b.time;
        // Numeric unix timestamps
        if (typeof ta === 'number' && typeof tb === 'number') return ta - tb;
        // Business-day objects
        if (ta && tb && typeof ta === 'object' && typeof tb === 'object' && ta.year && tb.year) {
            if (ta.year !== tb.year) return ta.year - tb.year;
            if (ta.month !== tb.month) return ta.month - tb.month;
            return ta.day - tb.day;
        }
        // ISO/date strings
        var da = Date.parse(String(ta));
        var db = Date.parse(String(tb));
        if (isFinite(da) && isFinite(db)) return da - db;
        return String(ta).localeCompare(String(tb));
    });

    return normalized;
}

function _tvLooksLikeOhlcBars(rows) {
    if (!Array.isArray(rows) || !rows.length) return false;
    for (var i = 0; i < rows.length; i++) {
        var r = rows[i] || {};
        if (r.open !== undefined && r.high !== undefined && r.low !== undefined && r.close !== undefined) {
            return true;
        }
    }
    return false;
}

function _tvIsMainSeriesId(seriesId) {
    return String(seriesId || 'main') === 'main';
}

/**
 * Compute a baseValue price for Baseline series from the data range.
 * TradingView uses a percentage-based "Base level" (default 50%) which
 * places the baseline at that percentile of the min-max range.
 *
 * @param {Array} bars - OHLC or value bars
 * @param {number} [pct=50] - Base level percentage (0-100)
 * @returns {number} the price at the given percentile
 */
function _tvComputeBaselineValue(bars, pct) {
    if (typeof pct !== 'number' || !isFinite(pct)) pct = 50;
    if (!Array.isArray(bars) || !bars.length) return 0;
    var min = Infinity, max = -Infinity;
    for (var i = 0; i < bars.length; i++) {
        var b = bars[i] || {};
        var hi = (b.high !== undefined) ? Number(b.high) : ((b.close !== undefined) ? Number(b.close) : (b.value !== undefined ? Number(b.value) : NaN));
        var lo = (b.low !== undefined) ? Number(b.low) : ((b.close !== undefined) ? Number(b.close) : (b.value !== undefined ? Number(b.value) : NaN));
        if (isFinite(hi) && hi > max) max = hi;
        if (isFinite(lo) && lo < min) min = lo;
    }
    if (!isFinite(min) || !isFinite(max)) return 0;
    return min + (max - min) * (pct / 100);
}

/**
 * Resolve a TV display name (e.g. "Hollow candles") into the base
 * LightweightCharts series type, data source, and option overrides.
 *
 * Also accepts legacy base type names ("Candlestick", "Bar", "Histogram")
 * so callers never need to branch on old vs new naming.
 */
function _tvResolveChartStyle(styleName) {
    var s = String(styleName || 'Line');
    if (s === 'Bars')              return { seriesType: 'Bar',         source: 'close',      optionPatch: {} };
    if (s === 'Candles')           return { seriesType: 'Candlestick', source: 'close',      optionPatch: {} };
    if (s === 'Hollow candles')    return { seriesType: 'Candlestick', source: 'close',      optionPatch: { upColor: 'rgba(0, 0, 0, 0)' } };
    if (s === 'HLC bars')          return { seriesType: 'Bar',         source: 'hlc3',       optionPatch: {} };
    if (s === 'Line')              return { seriesType: 'Line',        source: 'close',      optionPatch: {} };
    if (s === 'Line with markers') return { seriesType: 'Line',        source: 'close',      optionPatch: { pointMarkersVisible: true } };
    if (s === 'Step line')         return { seriesType: 'Line',        source: 'close',      optionPatch: { lineType: 1 } };
    if (s === 'Area')              return { seriesType: 'Area',        source: 'close',      optionPatch: {} };
    if (s === 'HLC area')          return { seriesType: 'Area',        source: 'close',      optionPatch: {}, composite: 'hlcArea' };
    if (s === 'Baseline')          return { seriesType: 'Baseline',    source: 'close',      optionPatch: {} };
    if (s === 'Columns')           return { seriesType: 'Histogram',   source: 'close',      optionPatch: {} };
    if (s === 'High-low')          return { seriesType: 'Bar',         source: 'close',      optionPatch: {} };
    if (s === 'Heikin Ashi')       return { seriesType: 'Candlestick', source: 'heikinashi', optionPatch: {} };
    // Legacy base type names (backward compat)
    if (s === 'Candlestick')       return { seriesType: 'Candlestick', source: 'close',      optionPatch: {} };
    if (s === 'Bar')               return { seriesType: 'Bar',         source: 'close',      optionPatch: {} };
    if (s === 'Histogram')         return { seriesType: 'Histogram',   source: 'close',      optionPatch: {} };
    return { seriesType: 'Line', source: 'close', optionPatch: {} };
}

/**
 * Build the data array for a given chart display style from raw OHLC bars.
 *
 * Handles special transformations like HLC bars, High-low, HLC area,
 * and Heikin Ashi. Returns an array ready for series.setData().
 */
function _tvBuildBarsForChartStyle(rawBars, styleName) {
    var src = Array.isArray(rawBars) ? rawBars : [];
    if (!src.length) return [];

    var cfg = _tvResolveChartStyle(styleName);
    var seriesType = cfg.seriesType;
    var source = cfg.source;

    var wantsValue = (seriesType === 'Line' || seriesType === 'Area' ||
                      seriesType === 'Baseline' || seriesType === 'Histogram');

    // Helper: extract a numeric value from a bar field
    function num(v, fb) {
        var n = Number(v);
        return isFinite(n) ? n : fb;
    }

    // Helper: compute source value from a bar
    function srcVal(row) {
        var r = row || {};
        var o = num(r.open, num(r.value, null));
        var h = num(r.high, o);
        var l = num(r.low, o);
        var c = num(r.close, num(r.value, o));
        if (source === 'hlc3') return (h + l + c) / 3;
        return c;
    }

    // --- Heikin Ashi transform ---
    if (source === 'heikinashi') {
        var ha = [];
        var prevHaOpen = null, prevHaClose = null;
        for (var i = 0; i < src.length; i++) {
            var b = src[i] || {};
            if (b.time == null) continue;
            var o = num(b.open, num(b.value, null));
            var h = num(b.high, o);
            var l = num(b.low, o);
            var c = num(b.close, num(b.value, o));
            if (o === null || !isFinite(o)) continue;

            var haClose = (o + h + l + c) / 4;
            var haOpen = (prevHaOpen !== null) ? (prevHaOpen + prevHaClose) / 2 : (o + c) / 2;
            var haHigh = Math.max(h, haOpen, haClose);
            var haLow = Math.min(l, haOpen, haClose);

            ha.push({ time: b.time, open: haOpen, high: haHigh, low: haLow, close: haClose });
            prevHaOpen = haOpen;
            prevHaClose = haClose;
        }
        return ha;
    }

    var out = [];
    var prevClose = null;

    for (var j = 0; j < src.length; j++) {
        var row = src[j] || {};
        if (row.time == null) continue;

        if (wantsValue) {
            var v = srcVal(row);
            if (v === null || !isFinite(v)) continue;
            out.push({ time: row.time, value: v });
            continue;
        }

        // OHLC series
        var ro = num(row.open, num(row.value, null));
        var rh = num(row.high, ro);
        var rl = num(row.low, ro);
        var rc = num(row.close, num(row.value, ro));
        if (ro === null || !isFinite(ro)) continue;

        var fOpen = ro, fHigh = rh, fLow = rl, fClose = rc;

        if (styleName === 'HLC bars') {
            var hlc = (rh + rl + rc) / 3;
            fOpen = (prevClose !== null) ? prevClose : hlc;
            fClose = hlc;
            fHigh = Math.max(fOpen, fClose, rh);
            fLow = Math.min(fOpen, fClose, rl);
            prevClose = fClose;
        } else if (styleName === 'High-low') {
            fOpen = rl;
            fClose = rh;
            fHigh = rh;
            fLow = rl;
        } else {
            prevClose = rc;
        }

        out.push({ time: row.time, open: fOpen, high: fHigh, low: fLow, close: fClose });
    }
    return out;
}

function _tvNormalizeSingleBarForSeriesType(bar, seriesType) {
    var arr = _tvNormalizeBarsForSeriesType([bar], seriesType);
    if (!arr.length) return null;
    var out = arr[0];
    if (seriesType === 'Histogram' && bar && bar.color !== undefined) {
        out.color = bar.color;
    }
    return out;
}

/**
 * Measure chart host dimensions, walking ancestors if the immediate
 * container has not been laid out yet.
 *
 * @param {HTMLElement} container
 * @returns {{ width: number, height: number }}
 */
function _tvMeasureContainerSize(container) {
    var width = container ? (container.clientWidth || 0) : 0;
    var height = container ? (container.clientHeight || 0) : 0;

    var cursor = container ? container.parentElement : null;
    var hops = 0;
    while ((width <= 0 || height <= 0) && cursor && hops < 8) {
        width = Math.max(width, cursor.clientWidth || 0);
        height = Math.max(height, cursor.clientHeight || 0);
        cursor = cursor.parentElement;
        hops += 1;
    }

    return {
        width: Math.max(width, 300),
        height: Math.max(height, 320),
    };
}

/**
 * Force a resize + fit pass after layout settles.
 *
 * @param {{ chart: Object, container: HTMLElement }} entry
 */
function _tvScheduleVisibilityRecovery(entry) {
    if (!entry || !entry.chart || !entry.container) return;

    function recoverOnce() {
        if (!entry.chart || !entry.container) return;
        var size = _tvMeasureContainerSize(entry.container);
        if (typeof entry.chart.resize === 'function') {
            entry.chart.resize(Math.floor(size.width), Math.floor(size.height));
        }
        // Skip fitContent when a default time-range zoom is pending or applied.
        if (!entry._initialRangeApplied) {
            try {
                entry.chart.timeScale().fitContent();
            } catch (e) {
                // no-op: fitContent is best-effort recovery only
            }
        }
    }

    setTimeout(recoverOnce, 0);
    if (typeof window.requestAnimationFrame === 'function') {
        window.requestAnimationFrame(function() {
            window.requestAnimationFrame(recoverOnce);
        });
    }
    setTimeout(recoverOnce, 120);
}

