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

