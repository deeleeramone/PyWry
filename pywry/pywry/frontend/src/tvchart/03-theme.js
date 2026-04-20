
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
    var base = {
        layout: {
            background: { type: LightweightCharts.ColorType.Solid, color: palette.background },
            textColor: palette.textColor,
            attributionLogo: false,
            panes: {
                separatorColor: separatorColor,
                separatorHoverColor: separatorHoverColor,
            },
        },
        grid: palette.grid,
        crosshair: palette.crosshair,
        rightPriceScale: {
            borderColor: palette.grid.vertLines.color,
            textColor: palette.textColor,
            scaleMargins: { top: 0.1, bottom: 0.1 },
        },
        leftPriceScale: {
            borderColor: palette.grid.vertLines.color,
            textColor: palette.textColor,
        },
        timeScale: {
            borderColor: palette.grid.vertLines.color,
            timeVisible: false,
            secondsVisible: false,
        },
        localization: { locale: 'en-US' },
    };
    base = _tvMerge(base, _tvInteractiveNavigationOptions());
    return chartOptions ? _tvMerge(base, chartOptions) : base;
}

