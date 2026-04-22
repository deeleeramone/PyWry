
// ---------------------------------------------------------------------------
// Theme detection — determines current theme from DOM state
// ---------------------------------------------------------------------------
function _tvDetectTheme() {
    var root = document.documentElement;
    if (root.classList.contains('light') || root.classList.contains('pywry-theme-light')) {
        return 'light';
    }
    return 'dark';
}

// ---------------------------------------------------------------------------
// Theme palettes (built from CSS variables at runtime - NO HARD-CODED VALUES)
// All values are loaded from CSS variables defined in tvchart.css
// See: pywry/pywry/frontend/style/tvchart.css for theme definitions
// ---------------------------------------------------------------------------

function _getTvchartTheme(themeName) {
    // All colors come from CSS variables - no hard-coded fallbacks
    var bg = _cssVar('--pywry-tvchart-bg');
    var text = _cssVar('--pywry-tvchart-text');
    var upColor = _cssVar('--pywry-tvchart-up');
    var downColor = _cssVar('--pywry-tvchart-down');
    var borderUp = _cssVar('--pywry-tvchart-border-up');
    var borderDown = _cssVar('--pywry-tvchart-border-down');
    var wickUp = _cssVar('--pywry-tvchart-wick-up');
    var wickDown = _cssVar('--pywry-tvchart-wick-down');
    var crosshairColor = _cssVar('--pywry-tvchart-crosshair');
    var gridVert = _cssVar('--pywry-tvchart-grid-vert');
    var gridHorz = _cssVar('--pywry-tvchart-grid-horz');
    var volUp = _cssVar('--pywry-tvchart-vol-up');
    var volDown = _cssVar('--pywry-tvchart-volume-down');
    
    return {
        background: bg,
        textColor: text,
        upColor: upColor,
        downColor: downColor,
        borderUpColor: borderUp,
        borderDownColor: borderDown,
        wickUpColor: wickUp,
        wickDownColor: wickDown,
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: { color: crosshairColor, width: 1, style: LightweightCharts.LineStyle.Dashed, visible: false, labelVisible: true },
            horzLine: { color: crosshairColor, width: 1, style: LightweightCharts.LineStyle.Dashed, visible: false, labelVisible: false },
        },
        grid: {
            vertLines: { color: gridVert, visible: true },
            horzLines: { color: gridHorz, visible: true },
        },
        volumeUp: volUp,
        volumeDown: volDown,
    };
}

var TVCHART_THEMES = {
    _get: function(themeName) {
        return _getTvchartTheme(themeName);
    },
};

function _tvMerge(base, extra) {
    var out;
    if (Array.isArray(base)) {
        out = base.slice();
    } else {
        out = {};
        if (base && typeof base === 'object') {
            var bKeys = Object.keys(base);
            for (var bi = 0; bi < bKeys.length; bi++) {
                var bk = bKeys[bi];
                var bv = base[bk];
                if (Array.isArray(bv)) out[bk] = bv.slice();
                else if (bv && typeof bv === 'object') out[bk] = _tvMerge({}, bv);
                else out[bk] = bv;
            }
        }
    }
    if (!extra || typeof extra !== 'object') return out;
    var keys = Object.keys(extra);
    for (var i = 0; i < keys.length; i++) {
        var k = keys[i];
        var v = extra[k];
        if (v && typeof v === 'object' && !Array.isArray(v)) {
            out[k] = _tvMerge(out[k] || {}, v);
        } else if (Array.isArray(v)) {
            out[k] = v.slice();
        } else {
            out[k] = v;
        }
    }
    return out;
}

function _tvBuildChartOptions(chartOptions, theme) {
    var palette = TVCHART_THEMES._get(theme || 'dark');
    var separatorColor = _cssVar('--pywry-tvchart-separator') || 'rgba(255,255,255,0.06)';
    var separatorHoverColor = _cssVar('--pywry-tvchart-separator-hover') || 'rgba(255,255,255,0.15)';
    var gridLineColor = palette.grid.vertLines.color;

    // Full LWC ``ChartOptionsImpl`` coverage — every option the library
    // accepts has a matching default here so `payload.chartOptions` can
    // override any of them without falling through to LWC's library
    // default.  Grouped per the interface sections on the docs page.
    var priceScaleCommon = {
        borderColor: gridLineColor,
        textColor: palette.textColor,
        // `mode` values: 0=Normal, 1=Logarithmic, 2=Percentage,
        //                3=IndexedTo100.  Default to Normal.
        mode: LightweightCharts.PriceScaleMode
            ? LightweightCharts.PriceScaleMode.Normal
            : 0,
        autoScale: true,
        invertScale: false,
        alignLabels: true,
        entireTextOnly: false,
        ticksVisible: true,
        visible: true,
        minimumWidth: 0,
        borderVisible: true,
        scaleMargins: { top: 0.1, bottom: 0.1 },
    };

    var base = {
        // ---- Layout ------------------------------------------------------
        layout: {
            background: { type: LightweightCharts.ColorType.Solid, color: palette.background },
            textColor: palette.textColor,
            fontSize: 12,
            fontFamily: "-apple-system, BlinkMacSystemFont, 'Trebuchet MS', Roboto, sans-serif",
            attributionLogo: false,
            colorSpace: 'srgb',
            colorParsers: [],
            panes: {
                separatorColor: separatorColor,
                separatorHoverColor: separatorHoverColor,
                enableResize: true,
            },
        },

        // ---- Price scales ------------------------------------------------
        rightPriceScale: _tvMerge(priceScaleCommon, {}),
        leftPriceScale: _tvMerge(priceScaleCommon, { visible: false }),
        overlayPriceScales: _tvMerge(priceScaleCommon, { scaleMargins: { top: 0.1, bottom: 0.1 } }),

        // ---- Time scale --------------------------------------------------
        timeScale: {
            borderColor: gridLineColor,
            borderVisible: true,
            visible: true,
            timeVisible: false,
            secondsVisible: false,
            rightOffset: 12,
            barSpacing: 6,
            minBarSpacing: 0.5,
            fixLeftEdge: false,
            fixRightEdge: false,
            lockVisibleTimeRangeOnResize: false,
            rightBarStaysOnScroll: false,
            shiftVisibleRangeOnNewBar: true,
            allowShiftVisibleRangeOnWhitespaceReplacement: false,
            uniformDistribution: false,
            minimumHeight: 0,
            allowBoldLabels: true,
            tickMarkMaxCharacterLength: undefined,
            ignoreWhitespaceIndices: false,
        },

        // ---- Crosshair / grid -------------------------------------------
        crosshair: palette.crosshair,
        grid: palette.grid,

        // ---- Interaction -------------------------------------------------
        kineticScroll: {
            touch: true,
            mouse: false,
        },
        trackingMode: {
            exitMode: LightweightCharts.TrackingModeExitMode
                ? LightweightCharts.TrackingModeExitMode.OnTouchEnd
                : 1,
        },

        // ---- Pane management --------------------------------------------
        addDefaultPane: true,

        // ---- Localization ------------------------------------------------
        // Formatters stay undefined so LWC falls back to Intl w/ the
        // chart's locale — callers can pass custom ``priceFormatter``
        // and ``timeFormatter`` via payload.chartOptions.localization.
        localization: {
            locale: 'en-US',
            dateFormat: "yyyy-MM-dd",
        },
    };

    base = _tvMerge(base, _tvInteractiveNavigationOptions());
    return chartOptions ? _tvMerge(base, chartOptions) : base;
}

// ---------------------------------------------------------------------------
// Specialised chart builders — same palette defaults as `_tvBuildChartOptions`
// but the horizontal scale is a NUMBER (not a Time).  These feed the two
// alternative LWC factories that plot data against a non-temporal X axis:
//
//   createOptionsChart       → numeric "price" / "strike" axis.  Used for
//                              option-chain payoff diagrams, IV smile/skew,
//                              volume-by-strike, market-profile histograms.
//
//   createYieldCurveChart    → numeric "tenor in months" axis with linear
//                              spacing.  Used for treasury / SOFR / OIS /
//                              swap / credit curves and any term-structure
//                              (contango/backwardation) visualisation.
// ---------------------------------------------------------------------------

function _tvBuildPriceChartOptions(chartOptions, theme) {
    var base = _tvBuildChartOptions(null, theme);
    // `PriceChartLocalizationOptions` replaces the timeFormatter with a
    // price-aware formatter.  We don't override the default formatter,
    // but drop the dateFormat field (not applicable with a price axis).
    if (base.localization) {
        delete base.localization.dateFormat;
    }
    // Price-axis charts don't need "timeVisible" on the horizontal scale.
    if (base.timeScale) {
        base.timeScale.timeVisible = false;
        base.timeScale.secondsVisible = false;
    }
    return chartOptions ? _tvMerge(base, chartOptions) : base;
}

function _tvBuildYieldCurveChartOptions(chartOptions, theme) {
    var base = _tvBuildChartOptions(null, theme);
    if (base.localization) {
        delete base.localization.dateFormat;
        // Custom tenor formatter — converts raw month count into the
        // TradingView standard "1M / 6M / 1Y / 2Y / 10Y" label.  LWC
        // ships a default formatter for yield-curve charts but we
        // define it explicitly so callers can override it via
        // localization.timeFormatter without reaching into yieldCurve.
        base.localization.timeFormatter = function(months) {
            var n = Number(months);
            if (!isFinite(n)) return String(months);
            if (n < 12) return n + 'M';
            if (n % 12 === 0) return (n / 12) + 'Y';
            return (n / 12).toFixed(1) + 'Y';
        };
    }
    // Yield-curve defaults — match LWC and expose a custom tenor-label
    // formatter here too so the specialty factory has both forms.
    base.yieldCurve = {
        baseResolution: 1,     // one month per step
        minimumTimeRange: 120, // 10 years default visible range
        startTimeRange: 0,
        formatTime: function(months) {
            var n = Number(months);
            if (!isFinite(n)) return String(months);
            if (n < 12) return n + 'M';
            if (n % 12 === 0) return (n / 12) + 'Y';
            return (n / 12).toFixed(1) + 'Y';
        },
    };
    if (base.timeScale) {
        base.timeScale.timeVisible = false;
        base.timeScale.secondsVisible = false;
        // Breathing room on both sides so line markers at 1M and 30Y
        // aren't clipped by the axis labels.
        base.timeScale.rightOffset = 2;
        // Yield curves have irregular tenor spacing — ignore whitespace
        // indices so the crosshair snaps to real points only.
        base.timeScale.ignoreWhitespaceIndices = true;
    }
    return chartOptions ? _tvMerge(base, chartOptions) : base;
}

