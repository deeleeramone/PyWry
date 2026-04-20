// ---------------------------------------------------------------------------
// Session (RTH/ETH) toggle  &  Timezone selector  —  bottom toolbar
// ---------------------------------------------------------------------------

var _tvTimezoneMenu = null;

// ── Timezone list ──────────────────────────────────────────────────────────
// Labels are city names only — UTC offsets are computed dynamically so they
// reflect the current DST state when the menu is opened.
var _TV_TIMEZONE_LIST = [
    { value: 'exchange', label: 'Exchange' },
    null, // separator
    { value: 'Etc/UTC',              label: 'UTC' },
    null,
    { value: 'Pacific/Honolulu',     label: 'Honolulu' },
    { value: 'America/Anchorage',    label: 'Anchorage' },
    { value: 'America/Los_Angeles',  label: 'Los Angeles' },
    { value: 'America/Phoenix',      label: 'Phoenix' },
    { value: 'America/Denver',       label: 'Denver' },
    { value: 'America/Chicago',      label: 'Chicago' },
    { value: 'America/New_York',     label: 'New York' },
    { value: 'America/Toronto',      label: 'Toronto' },
    { value: 'America/Sao_Paulo',    label: 'São Paulo' },
    { value: 'America/Argentina/Buenos_Aires', label: 'Buenos Aires' },
    null,
    { value: 'Atlantic/Reykjavik',   label: 'Reykjavik' },
    { value: 'Europe/London',        label: 'London' },
    { value: 'Europe/Madrid',        label: 'Madrid' },
    { value: 'Europe/Paris',         label: 'Paris' },
    { value: 'Europe/Berlin',        label: 'Berlin' },
    { value: 'Europe/Zurich',        label: 'Zurich' },
    { value: 'Europe/Athens',        label: 'Athens' },
    { value: 'Europe/Helsinki',      label: 'Helsinki' },
    { value: 'Europe/Istanbul',      label: 'Istanbul' },
    { value: 'Europe/Moscow',        label: 'Moscow' },
    null,
    { value: 'Asia/Dubai',           label: 'Dubai' },
    { value: 'Asia/Kolkata',         label: 'Kolkata' },
    { value: 'Asia/Bangkok',         label: 'Bangkok' },
    { value: 'Asia/Shanghai',        label: 'Shanghai' },
    { value: 'Asia/Hong_Kong',       label: 'Hong Kong' },
    { value: 'Asia/Singapore',       label: 'Singapore' },
    { value: 'Asia/Taipei',          label: 'Taipei' },
    { value: 'Asia/Seoul',           label: 'Seoul' },
    { value: 'Asia/Tokyo',           label: 'Tokyo' },
    null,
    { value: 'Australia/Perth',      label: 'Perth' },
    { value: 'Australia/Sydney',     label: 'Sydney' },
    { value: 'Pacific/Auckland',     label: 'Auckland' },
];

/** Compute the current UTC offset string for an IANA timezone, e.g. "UTC-4". */
function _tvCurrentUtcOffset(tz) {
    if (!tz || tz === 'Etc/UTC' || tz === 'UTC') return '';
    try {
        var parts = new Date().toLocaleString('en-US', {
            timeZone: tz, timeZoneName: 'shortOffset',
        }).split(' ');
        // Last token is like "GMT-4", "GMT+5:30", "GMT+0", etc.
        var raw = parts[parts.length - 1] || '';
        return raw.replace(/^GMT/, 'UTC');
    } catch (e) { return ''; }
}

// ── Helpers ────────────────────────────────────────────────────────────────

// Track which chart's menu is currently active — set by toggle functions,
// consumed by menu open/select functions so they scope to the right chart.
var _tvActiveMenuChartId = null;

function _tvGetFirstEntry(chartId) {
    var cid = chartId || _tvActiveMenuChartId;
    if (cid && window.__PYWRY_TVCHARTS__[cid]) {
        return window.__PYWRY_TVCHARTS__[cid];
    }
    var ids = Object.keys(window.__PYWRY_TVCHARTS__ || {});
    if (!ids.length) return null;
    return window.__PYWRY_TVCHARTS__[ids[0]];
}

/** Return the main symbol info from whichever source has it. */
function _tvGetMainSymbolInfo() {
    var entry = _tvGetFirstEntry();
    if (!entry) return {};
    // _mainSymbolInfo is set on symbol change; _resolvedSymbolInfo.main on initial load.
    return entry._mainSymbolInfo
        || (entry._resolvedSymbolInfo && entry._resolvedSymbolInfo.main)
        || {};
}

function _tvGetExchangeTimezone() {
    var info = _tvGetMainSymbolInfo();
    return info.timezone || 'Etc/UTC';
}

/** The IANA tz the chart should currently use. */
function _tvGetActiveTimezone() {
    var entry = _tvGetFirstEntry();
    if (!entry) return 'Etc/UTC';
    var sel = entry._selectedTimezone || 'exchange';
    return sel === 'exchange' ? _tvGetExchangeTimezone() : sel;
}

/** True when current interval is intraday (seconds/minutes/hours). */
function _tvIsCurrentIntervalIntraday() {
    var ids = Object.keys(window.__PYWRY_TVCHARTS__ || {});
    var chartId = ids.length ? ids[0] : 'main';
    var interval = _tvCurrentInterval(chartId);
    var raw = String(interval || '').trim().toLowerCase();
    if (!raw) return false;
    // Daily and above: 1d, 1w, 1M, 3M, 6M, 12M
    if (/^\d*[dwm]$/i.test(raw) && !/m(in)?$/i.test(raw)) {
        // Check if it's minutes (ends in 'm' lowercase with no further letter)
        // '1m' is 1-minute, '1M' is 1-month
        var lastChar = raw.charAt(raw.length - 1);
        if (lastChar === 'd' || lastChar === 'w') return false;
        // For 'm' / 'M': uppercase M = month, lowercase m = minute
        var origLast = String(interval).charAt(String(interval).length - 1);
        if (origLast === 'M') return false; // month
        return true; // minute
    }
    // Numeric-only → minutes
    if (/^\d+$/.test(raw)) return true;
    // Contains 'min' or 'h' or 's' → intraday
    if (/min|hour|sec|^[0-9]+[hms]/i.test(raw)) return true;
    return false;
}

/** Short label for the tz button. */
function _tvTzButtonLabel(selected) {
    if (!selected || selected === 'exchange') return 'Exchange';
    if (selected === 'Etc/UTC' || selected === 'UTC') return 'UTC';
    // Show city name only
    var parts = selected.split('/');
    return parts[parts.length - 1].replace(/_/g, ' ');
}

// ── Session selector (RTH / ETH) ───────────────────────────────────────

var _tvSessionMenu = null;
var _tvSessionMenuClickAway = null;
var _tvPersistedSessionMode = 'ETH';

// ── Session filtering helpers ──────────────────────────────────────────

/**
 * Filter bars to only those whose exchange-local time falls within
 * the given session window string(s).
 *
 * @param {Array} bars   - bar objects with .time (unix seconds)
 * @param {string} sessionStr - e.g. "0930-1600" or "0000-1700,1800-2359"
 * @param {string} tz    - IANA timezone, e.g. "America/New_York"
 * @returns {Array} filtered bars
 */
function _tvFilterBarsBySession(bars, sessionStr, tz) {
    if (!bars || !bars.length || !sessionStr) return bars || [];
    if (sessionStr === '24x7') return bars;

    // TradingView session strings may include a ``:weekdays`` suffix
    // (``0930-1600:23456`` = Mon-Fri) and be separated by either ``,`` or
    // ``|`` in multi-session feeds.  Normalise both so the regex below
    // only has to handle ``HHMM-HHMM``.
    var ranges = sessionStr.split(/[,|]/);
    var parsed = [];
    for (var i = 0; i < ranges.length; i++) {
        var r = ranges[i].trim();
        var colonIdx = r.indexOf(':');
        if (colonIdx >= 0) r = r.substring(0, colonIdx);
        var m = r.match(/^(\d{2})(\d{2})-(\d{2})(\d{2})$/);
        if (m) {
            parsed.push({
                s: parseInt(m[1], 10) * 60 + parseInt(m[2], 10),
                e: parseInt(m[3], 10) * 60 + parseInt(m[4], 10),
            });
        }
    }
    if (!parsed.length) return bars;

    var fmt;
    try {
        fmt = new Intl.DateTimeFormat('en-US', {
            timeZone: tz, hour: 'numeric', minute: 'numeric', hour12: false,
        });
    } catch (err) { return bars; }

    var out = [];
    for (var j = 0; j < bars.length; j++) {
        var ts = bars[j].time;
        if (typeof ts !== 'number') continue;
        var d = new Date(ts < 1e12 ? ts * 1000 : ts);
        var parts = fmt.formatToParts(d);
        var h = 0, mn = 0;
        for (var p = 0; p < parts.length; p++) {
            if (parts[p].type === 'hour') h = parseInt(parts[p].value, 10);
            if (parts[p].type === 'minute') mn = parseInt(parts[p].value, 10);
        }
        if (h === 24) h = 0;
        var localMin = h * 60 + mn;
        var ok = false;
        for (var k = 0; k < parsed.length; k++) {
            var r = parsed[k];
            if (r.s <= r.e) {
                if (localMin >= r.s && localMin < r.e) { ok = true; break; }
            } else {
                if (localMin >= r.s || localMin < r.e) { ok = true; break; }
            }
        }
        if (ok) out.push(bars[j]);
    }
    return out;
}

/**
 * Check if a single bar timestamp falls within the current RTH session.
 * Returns true if session is ETH (no filter), or if the bar is inside
 * the regular session window.  Returns false only when RTH is active
 * and the bar time is outside the regular session.
 *
 * @param {number} barTime - unix seconds
 * @returns {boolean}
 */
function _tvIsBarInCurrentSession(barTime) {
    var entry = _tvGetFirstEntry();
    if (!entry) return true;
    var mode = entry._sessionMode || 'ETH';
    if (mode !== 'RTH') return true;

    var info = _tvGetMainSymbolInfo();
    // For RTH-only filtering we want the regular-hours window
    // explicitly — ``info.session`` is the FULL trading hours string
    // (may include pre + regular + post concatenated), while
    // ``info.session_regular`` is just the core 0930-1600 slot.  When
    // the provider only ships ``info.session``, fall back to that.
    var sessionStr = info.session_regular || info.session;
    if (!sessionStr || sessionStr === '24x7') return true;

    var tz = info.timezone || _tvGetExchangeTimezone();
    var filtered = _tvFilterBarsBySession([{ time: barTime }], sessionStr, tz);
    return filtered.length > 0;
}

/**
 * Apply session (RTH / ETH) filtering to every series in the chart.
 * _seriesRawData always holds the full (ETH) bars; this function
 * either passes them through (ETH) or filters them (RTH) before
 * calling series.setData().
 */
function _tvApplySessionFilter() {
    var entry = _tvGetFirstEntry();
    if (!entry) return;

    var mode = entry._sessionMode || 'ETH';
    var info = _tvGetMainSymbolInfo();
    // For RTH-only filtering we want the regular-hours window
    // explicitly — ``info.session`` is the FULL trading hours string
    // (may include pre + regular + post concatenated), while
    // ``info.session_regular`` is just the core 0930-1600 slot.  When
    // the provider only ships ``info.session``, fall back to that.
    var sessionStr = info.session_regular || info.session;
    var tz = info.timezone || _tvGetExchangeTimezone();
    var sids = Object.keys(entry.seriesMap || {});
    entry._seriesDisplayData = entry._seriesDisplayData || {};

    // Skip derived series that have no ``_seriesRawData`` entry —
    // indicator lines are computed from the main bars and get refreshed
    // below via the global recompute; session filter only applies to
    // chart-data series (main + compare overlays).
    for (var i = 0; i < sids.length; i++) {
        var sid = sids[i];
        if (typeof _activeIndicators === 'object' && _activeIndicators[sid]) continue;
        var series = entry.seriesMap[sid];
        var raw = entry._seriesRawData[sid];
        if (!series || !raw || !raw.length) continue;

        var display = (mode === 'RTH' && sessionStr && sessionStr !== '24x7')
            ? _tvFilterBarsBySession(raw, sessionStr, tz)
            : raw;
        entry._seriesDisplayData[sid] = display;
        series.setData(display);

        // Volume histogram must match
        var vol = entry.volumeMap && entry.volumeMap[sid];
        if (vol) {
            var src = (entry._seriesCanonicalRawData && entry._seriesCanonicalRawData[sid]) || raw;
            var fSrc = (mode === 'RTH' && sessionStr && sessionStr !== '24x7')
                ? _tvFilterBarsBySession(src, sessionStr, tz)
                : src;
            var vd = _tvExtractVolumeFromBars(fSrc, entry.theme, entry);
            vol.setData(vd && vd.length ? vd : []);
        }
    }

    // Find the chartId for downstream per-chart refreshes.
    var _sessIds = Object.keys(window.__PYWRY_TVCHARTS__ || {});
    var _sessChartId = null;
    for (var _si = 0; _si < _sessIds.length; _si++) {
        if (window.__PYWRY_TVCHARTS__[_sessIds[_si]] === entry) { _sessChartId = _sessIds[_si]; break; }
    }

    // fitContent FIRST so the visible logical range re-seats on the
    // shorter filtered bar set — otherwise _tvRefreshVisibleVolumeProfiles
    // reads a stale range that points PAST the end of the new array, the
    // compute clamps to one bar at index N-1, and VPVR ends up showing a
    // single bar's volume (looks like "877K up, 0 down" on an RTH toggle
    // when the previous ETH view was scrolled right).
    if (entry.chart) entry.chart.timeScale().fitContent();

    // Recompute every indicator against the now-filtered bar set so
    // SMA(9) etc. reflects 9 RTH bars, not 9 ETH bars with an overnight
    // gap baked in.  _tvSeriesRawData returns _seriesDisplayData when
    // _sessionMode === 'RTH', so compute paths pick up the right source
    // automatically.
    if (_sessChartId && typeof _tvRecomputeIndicatorsForChart === 'function') {
        try { _tvRecomputeIndicatorsForChart(_sessChartId, 'main'); } catch (_e) {}
    }

    // Volume Profile Visible Range reads from _seriesRawData inside
    // _tvRefreshVisibleVolumeProfiles — the above raw-data shim kicks in
    // there too, so the profile re-pins over the filtered bar set.  Now
    // that fitContent has updated the visible range, the VP compute sees
    // the right [0, N-1] span.
    if (_sessChartId && typeof _tvRefreshVisibleVolumeProfiles === 'function') {
        try { _tvRefreshVisibleVolumeProfiles(_sessChartId); } catch (_e2) {}
    }

    if (_sessChartId) _tvRenderHoverLegend(_sessChartId, null);
}

function _tvToggleSessionMenu() {
    _tvActiveMenuChartId = _tvResolveChartIdFromElement(event ? event.target : null);
    if (_tvSessionMenu) {
        _tvCloseSessionMenu();
        return;
    }
    _tvOpenSessionMenu();
}

function _tvCloseSessionMenu() {
    if (_tvSessionMenu && _tvSessionMenu.parentNode) {
        _tvSessionMenu.parentNode.removeChild(_tvSessionMenu);
    }
    _tvSessionMenu = null;
    if (_tvSessionMenuClickAway) {
        document.removeEventListener('mousedown', _tvSessionMenuClickAway, true);
        _tvSessionMenuClickAway = null;
    }
}

function _tvOpenSessionMenu() {
    _tvCloseSessionMenu();

    var entry = _tvGetFirstEntry();
    var current = (entry && entry._sessionMode) || 'ETH';

    var menu = document.createElement('div');
    menu.className = 'tvchart-tz-menu';
    _tvSessionMenu = menu;

    // Header
    var header = document.createElement('div');
    header.className = 'tvchart-session-menu-header';
    header.textContent = 'SESSIONS';
    menu.appendChild(header);

    var options = [
        { value: 'RTH', label: 'Regular trading hours' },
        { value: 'ETH', label: 'Extended trading hours' },
    ];

    for (var i = 0; i < options.length; i++) {
        var opt = options[i];
        var row = document.createElement('div');
        row.className = 'tvchart-tz-menu-item' + (opt.value === current ? ' selected' : '');
        row.setAttribute('data-session-value', opt.value);

        var check = document.createElement('span');
        check.className = 'tz-check';
        check.textContent = opt.value === current ? '\u2713' : '';
        row.appendChild(check);

        var label = document.createElement('span');
        label.textContent = opt.label;
        row.appendChild(label);

        (function(val) {
            row.addEventListener('click', function() {
                _tvSelectSessionMode(val);
                _tvCloseSessionMenu();
            });
        })(opt.value);

        menu.appendChild(row);
    }

    // Position above the session button
    var btn = _tvScopedById(_tvActiveMenuChartId, 'tvchart-session-btn');
    var _oc = _tvOverlayContainer(btn || menu);
    if (_oc !== document.body) menu.style.position = 'absolute';
    if (btn) {
        var _cs = _tvContainerSize(_oc);
        var rect = _tvContainerRect(_oc, btn.getBoundingClientRect());
        menu.style.left = Math.max(0, rect.left) + 'px';
        menu.style.bottom = (_cs.height - rect.top + 4) + 'px';
    }

    _oc.appendChild(menu);

    // Close on click-away
    _tvSessionMenuClickAway = function(e) {
        if (menu.contains(e.target)) return;
        if (btn && btn.contains(e.target)) return;
        _tvCloseSessionMenu();
    };
    document.addEventListener('mousedown', _tvSessionMenuClickAway, true);
}

function _tvSelectSessionMode(value) {
    var entry = _tvGetFirstEntry();
    if (!entry) return;

    if (entry._sessionMode === value) return;
    entry._sessionMode = value;
    _tvPersistedSessionMode = value;

    // Update button label
    var btn = _tvScopedById(_tvActiveMenuChartId, 'tvchart-session-btn');
    if (btn) {
        var lbl = btn.querySelector('.tvchart-bottom-btn-label');
        if (lbl) lbl.textContent = value;
        btn.classList.toggle('active', value === 'RTH');
    }

    // Apply local session filter — no round-trip to Python
    _tvApplySessionFilter();
}

/** Show/hide the session button based on: is intraday interval. */
function _tvUpdateSessionBtnVisibility() {
    var chartId = _tvActiveMenuChartId;
    var btn = _tvScopedById(chartId, 'tvchart-session-btn');
    if (!btn) return;

    var entry = _tvGetFirstEntry();
    if (!entry) { btn.style.display = 'none'; return; }

    btn.style.display = _tvIsCurrentIntervalIntraday() ? '' : 'none';
}

// ── Timezone selector ──────────────────────────────────────────────────────

function _tvToggleTimezoneMenu() {
    _tvActiveMenuChartId = _tvResolveChartIdFromElement(event ? event.target : null);
    if (_tvTimezoneMenu) {
        _tvCloseTimezoneMenu();
        return;
    }
    _tvOpenTimezoneMenu();
}

function _tvCloseTimezoneMenu() {
    if (_tvTimezoneMenu && _tvTimezoneMenu.parentNode) {
        _tvTimezoneMenu.parentNode.removeChild(_tvTimezoneMenu);
    }
    _tvTimezoneMenu = null;
    if (_tvTzMenuClickAway) {
        document.removeEventListener('mousedown', _tvTzMenuClickAway, true);
        _tvTzMenuClickAway = null;
    }
}

var _tvTzMenuClickAway = null;

function _tvOpenTimezoneMenu() {
    _tvCloseTimezoneMenu();

    var entry = _tvGetFirstEntry();
    var current = (entry && entry._selectedTimezone) || 'exchange';

    var menu = document.createElement('div');
    menu.className = 'tvchart-tz-menu';
    _tvTimezoneMenu = menu;

    for (var i = 0; i < _TV_TIMEZONE_LIST.length; i++) {
        var item = _TV_TIMEZONE_LIST[i];
        if (item === null) {
            var sep = document.createElement('div');
            sep.className = 'tvchart-tz-menu-sep';
            menu.appendChild(sep);
            continue;
        }
        var row = document.createElement('div');
        row.className = 'tvchart-tz-menu-item' + (item.value === current ? ' selected' : '');
        row.setAttribute('data-tz-value', item.value);

        var check = document.createElement('span');
        check.className = 'tz-check';
        check.textContent = item.value === current ? '✓' : '';
        row.appendChild(check);

        var label = document.createElement('span');
        var offset = _tvCurrentUtcOffset(item.value);
        label.textContent = offset ? item.label + ' (' + offset + ')' : item.label;
        row.appendChild(label);

        (function(val) {
            row.addEventListener('click', function() {
                _tvSelectTimezone(val);
                _tvCloseTimezoneMenu();
            });
        })(item.value);

        menu.appendChild(row);
    }

    // Position above the tz button
    var btn = _tvScopedById(_tvActiveMenuChartId, 'tvchart-tz-btn');
    var _oc = _tvOverlayContainer(btn || menu);
    if (_oc !== document.body) menu.style.position = 'absolute';
    if (btn) {
        var _cs = _tvContainerSize(_oc);
        var rect = _tvContainerRect(_oc, btn.getBoundingClientRect());
        menu.style.left = Math.max(0, rect.left) + 'px';
        menu.style.bottom = (_cs.height - rect.top + 4) + 'px';
    }

    _oc.appendChild(menu);

    // Close on click-away
    _tvTzMenuClickAway = function(e) {
        if (menu.contains(e.target)) return;
        if (btn && btn.contains(e.target)) return;
        _tvCloseTimezoneMenu();
    };
    document.addEventListener('mousedown', _tvTzMenuClickAway, true);
}

function _tvSelectTimezone(value) {
    var entry = _tvGetFirstEntry();
    if (!entry) return;
    entry._selectedTimezone = value;

    // Update button label
    var btn = _tvScopedById(_tvActiveMenuChartId, 'tvchart-tz-btn');
    if (btn) {
        var lbl = btn.querySelector('.tvchart-bottom-btn-label');
        if (lbl) lbl.textContent = _tvTzButtonLabel(value);
    }

    var tz = value === 'exchange' ? _tvGetExchangeTimezone() : value;

    // Update exchange clock
    _tvUpdateExchangeClock(entry, tz);

    // Update chart time axis formatters
    _tvApplyTimezoneToChart(entry, tz);
}

function _tvUpdateExchangeClock(entry, tz) {
    var clockEl = _tvScopedById(_tvActiveMenuChartId, 'tvchart-exchange-clock');
    if (!clockEl) return;

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
        } catch (e) { clockEl.textContent = ''; }
    }
    updateClock();
    if (entry._clockInterval) clearInterval(entry._clockInterval);
    entry._clockInterval = setInterval(updateClock, 1000);
}

function _tvApplyTimezoneToChart(entry, tz) {
    if (!entry || !entry.chart) return;
    try {
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
                tickMarkFormatter: function(time, tickType) {
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
    } catch (e) {
        if (typeof console !== 'undefined') console.warn('[PyWry TVChart] timezone apply error:', e);
    }
}

// ── Data-request augmentation ─────────────────────────────────────────────
// Patch _tvBuildIntervalRequestContext to include session & timezone fields.

(function() {
    if (typeof _tvBuildIntervalRequestContext !== 'function') return;
    var _origBuild = _tvBuildIntervalRequestContext;

    window._tvBuildIntervalRequestContext = function(chartId, interval) {
        var ctx = _origBuild(chartId, interval);
        var entry = _tvGetFirstEntry();
        if (entry) {
            ctx.session = entry._sessionMode || 'ETH';
        }
        ctx.timezone = _tvGetActiveTimezone();
        return ctx;
    };
    // Also update the plain name so callers that captured it locally still get the patched version
    _tvBuildIntervalRequestContext = window._tvBuildIntervalRequestContext;
})();

// ── Interval-change hook: update session button visibility ────────────────
// In widget mode, these handlers are registered per-bridge via
// _tvRegisterEventHandlers.  The global fallback here covers native-window
// mode only.
(function() {
    function _registerSessionHook() {
        var _bridge = window.pywry;
        if (!_bridge || !_bridge.on) return;
        _bridge.on('tvchart:interval-change', function() {
            _tvUpdateSessionBtnVisibility();
        });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _registerSessionHook);
    } else {
        setTimeout(_registerSessionHook, 0);
    }
})();

// ── Symbol-change hook: reset session/tz for new symbol ───────────────────
(function() {
    var _hookReady = function() {
        var _bridge = window.pywry;
        if (!_bridge || !_bridge.on) return;
        _bridge.on('tvchart:data-response', function() {
            // After data arrives, refresh session button visibility
            _tvUpdateSessionBtnVisibility();
            // Restore persisted session mode and re-apply filter
            if (_tvPersistedSessionMode !== 'ETH') {
                var _entry = _tvGetFirstEntry();
                if (_entry) {
                    _entry._sessionMode = _tvPersistedSessionMode;
                    var _btn = _tvScopedById(_tvActiveMenuChartId, 'tvchart-session-btn');
                    if (_btn) {
                        var _lbl = _btn.querySelector('.tvchart-bottom-btn-label');
                        if (_lbl) _lbl.textContent = _tvPersistedSessionMode;
                        _btn.classList.toggle('active', _tvPersistedSessionMode === 'RTH');
                    }
                }
                // Delay slightly to ensure series data is fully set
                setTimeout(_tvApplySessionFilter, 50);
            }
        });
    };
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _hookReady);
    } else {
        setTimeout(_hookReady, 0);
    }
})();

// ── On initial load: set session btn visibility once chart is ready ───────
(function() {
    function _initSessionTz() {
        _tvUpdateSessionBtnVisibility();
        // Ensure timezone button shows 'Exchange'
        var btn = document.getElementById('tvchart-tz-btn');
        if (btn) {
            var lbl = btn.querySelector('.tvchart-bottom-btn-label');
            if (lbl) lbl.textContent = 'Exchange';
        }
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(_initSessionTz, 200);
        });
    } else {
        setTimeout(_initSessionTz, 200);
    }
})();

// ---------------------------------------------------------------------------
// Scale-mode toggle buttons (%, log, auto) — bottom toolbar
// ---------------------------------------------------------------------------

function _tvApplyLogScale(isLog, chartId) {
    var ids = chartId ? [chartId] : Object.keys(window.__PYWRY_TVCHARTS__);
    for (var i = 0; i < ids.length; i++) {
        var entry = window.__PYWRY_TVCHARTS__[ids[i]];
        if (!entry || !entry.chart) continue;
        if (!entry._chartPrefs) entry._chartPrefs = {};
        entry._chartPrefs.logScale = isLog;
        // Log mode (1) is mutually exclusive with pct mode (2)
        if (isLog) entry._chartPrefs.pctScale = false;
        var scaleSide = _tvResolveScalePlacement(entry);
        entry.chart.priceScale(scaleSide).applyOptions({ mode: isLog ? 1 : 0 });
        _tvApplyCustomScaleSide(entry, scaleSide, { mode: isLog ? 1 : 0 });
    }
}

function _tvApplyAutoScale(isAuto, chartId) {
    var ids = chartId ? [chartId] : Object.keys(window.__PYWRY_TVCHARTS__);
    for (var i = 0; i < ids.length; i++) {
        var entry = window.__PYWRY_TVCHARTS__[ids[i]];
        if (!entry || !entry.chart) continue;
        if (!entry._chartPrefs) entry._chartPrefs = {};
        entry._chartPrefs.autoScale = isAuto;
        var scaleSide = _tvResolveScalePlacement(entry);
        entry.chart.priceScale(scaleSide).applyOptions({ autoScale: isAuto });
        _tvApplyCustomScaleSide(entry, scaleSide, { autoScale: isAuto });
    }
}

function _tvApplyPctScale(isPct, chartId) {
    var ids = chartId ? [chartId] : Object.keys(window.__PYWRY_TVCHARTS__);
    for (var i = 0; i < ids.length; i++) {
        var entry = window.__PYWRY_TVCHARTS__[ids[i]];
        if (!entry || !entry.chart) continue;
        if (!entry._chartPrefs) entry._chartPrefs = {};
        entry._chartPrefs.pctScale = isPct;
        // Pct mode (2) is mutually exclusive with log mode (1)
        if (isPct) entry._chartPrefs.logScale = false;
        var scaleSide = _tvResolveScalePlacement(entry);
        entry.chart.priceScale(scaleSide).applyOptions({ mode: isPct ? 2 : 0 });
        _tvApplyCustomScaleSide(entry, scaleSide, { mode: isPct ? 2 : 0 });
    }
}

function _tvToggleLogScale() {
    var chartId = _tvResolveChartIdFromElement(event ? event.target : null);
    var btn = _tvScopedById(chartId, 'tvchart-log-scale-btn');
    var isActive = btn && btn.classList.contains('active');
    var newState = !isActive;
    _tvApplyLogScale(newState, chartId);
    if (btn) btn.classList.toggle('active', newState);
    // Deactivate % if log is turned on (mutually exclusive)
    if (newState) {
        var pctBtn = _tvScopedById(chartId, 'tvchart-pct-scale-btn');
        if (pctBtn) pctBtn.classList.remove('active');
    }
}

function _tvToggleAutoScale() {
    var chartId = _tvResolveChartIdFromElement(event ? event.target : null);
    var btn = _tvScopedById(chartId, 'tvchart-auto-scale-btn');
    var isActive = btn && btn.classList.contains('active');
    var newState = !isActive;
    _tvApplyAutoScale(newState, chartId);
    if (btn) btn.classList.toggle('active', newState);
}

function _tvTogglePctScale() {
    var chartId = _tvResolveChartIdFromElement(event ? event.target : null);
    var btn = _tvScopedById(chartId, 'tvchart-pct-scale-btn');
    var isActive = btn && btn.classList.contains('active');
    var newState = !isActive;
    _tvApplyPctScale(newState, chartId);
    if (btn) btn.classList.toggle('active', newState);
    // Deactivate log if % is turned on (mutually exclusive)
    if (newState) {
        var logBtn = _tvScopedById(chartId, 'tvchart-log-scale-btn');
        if (logBtn) logBtn.classList.remove('active');
    }
}
