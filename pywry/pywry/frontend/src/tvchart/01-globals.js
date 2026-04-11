/* PyWry TradingView Lightweight Charts Defaults & Registry */

// Registry for all TV chart instances on the page
window.__PYWRY_TVCHARTS__ = window.__PYWRY_TVCHARTS__ || {};

// Unified component registry — any component can register with getData()
window.__PYWRY_COMPONENTS__ = window.__PYWRY_COMPONENTS__ || {};

// Datafeed protocol request registry — full TradingView Datafeed API surface
window.__PYWRY_TVCHART_DATAFEED__ = window.__PYWRY_TVCHART_DATAFEED__ || {
    seq: 0,
    pendingConfig: {},
    pendingSearch: {},
    pendingResolve: {},
    pendingHistory: {},
    pendingMarks: {},
    pendingTimescaleMarks: {},
    pendingServerTime: {},
    // subscribeBars: listenerGuid → { onTick, onResetCacheNeeded, symbolInfo, resolution }
    subscriptions: {},
};

// ---------------------------------------------------------------------------
// CSS variable reader — resolves theme-aware values at runtime for canvas ops
// ---------------------------------------------------------------------------
function _cssVar(name, fallback) {
    var val = getComputedStyle(document.documentElement).getPropertyValue(name);
    return val ? val.trim() : (fallback || '');
}

