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

// ---------------------------------------------------------------------------
// Bridge lookup — returns the pywry bridge for a given chart.
// In a multi-widget notebook each chart stores its own bridge reference.
// Falls back to the global window.pywry for native-window mode.
// ---------------------------------------------------------------------------
function _tvGetBridge(chartId) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (entry && entry.bridge) return entry.bridge;
    if (entry && entry.container) {
        var w = entry.container.closest && entry.container.closest('.pywry-widget');
        if (w && w._pywryInstance) return w._pywryInstance;
    }
    return window.pywry;
}

// ---------------------------------------------------------------------------
// Overlay container — returns the correct parent for fixed/absolute overlays.
// In a native window document.body IS the chart, so overlays go there.
// In an anywidget (notebook), the chart lives inside a .pywry-widget element;
// appending to document.body would place the overlay outside the widget entirely.
// ---------------------------------------------------------------------------
function _tvOverlayContainer(chartIdOrEl) {
    // Accept a DOM element — walk up to find .pywry-widget
    if (chartIdOrEl && chartIdOrEl.nodeType) {
        var w = chartIdOrEl.closest && chartIdOrEl.closest('.pywry-widget');
        if (w) return w;
        return document.body;
    }
    var entry = window.__PYWRY_TVCHARTS__ && window.__PYWRY_TVCHARTS__[chartIdOrEl || 'main'];
    if (entry && entry.container) {
        var widget = entry.container.closest('.pywry-widget');
        if (widget) return widget;
    }
    // Fallback: walk from any chart container on the page
    var el = document.querySelector('.pywry-tvchart-container');
    if (el) {
        var w = el.closest('.pywry-widget');
        if (w) return w;
    }
    return document.body;
}

// ---------------------------------------------------------------------------
// Append an overlay to the correct container AND force position:absolute when
// inside .pywry-widget so it stays contained (cannot rely on CSS file alone
// since stylesheets may be cached from a previous build).
// ---------------------------------------------------------------------------
function _tvAppendOverlay(chartIdOrEl, overlay) {
    var container = _tvOverlayContainer(chartIdOrEl);
    if (container !== document.body) {
        overlay.style.position = 'absolute';
    }
    container.appendChild(overlay);
    return container;
}

// ---------------------------------------------------------------------------
// Convert a viewport-relative bounding rect to container-relative coords.
// When the container IS document.body the values pass through unchanged.
// ---------------------------------------------------------------------------
function _tvContainerRect(container, viewportRect) {
    if (container === document.body) return viewportRect;
    var cr = container.getBoundingClientRect();
    return {
        left:   viewportRect.left   - cr.left,
        top:    viewportRect.top    - cr.top,
        right:  viewportRect.right  - cr.left,
        bottom: viewportRect.bottom - cr.top,
        width:  viewportRect.width,
        height: viewportRect.height
    };
}

// Container inner dimensions — use instead of window.innerWidth/Height
function _tvContainerSize(container) {
    if (container === document.body) return { width: window.innerWidth, height: window.innerHeight };
    return { width: container.clientWidth, height: container.clientHeight };
}
