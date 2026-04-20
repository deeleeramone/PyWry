// Helper: sync hline price after coordinate edit
function _tvSyncPriceLinePrice(chartId, drawIdx, newPrice) {
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!ds || !entry) return;
    var d = ds.drawings[drawIdx];
    if (!d || d.type !== 'hline') return;
    // Remove old native price line and recreate
    if (ds.priceLines[drawIdx]) {
        var pl = ds.priceLines[drawIdx];
        var ser = entry.seriesMap[pl.seriesId];
        if (ser) try { ser.removePriceLine(pl.priceLine); } catch(e) {}
    }
    var mainKey = Object.keys(entry.seriesMap)[0];
    if (mainKey && entry.seriesMap[mainKey]) {
        var newPl = entry.seriesMap[mainKey].createPriceLine({
            price: newPrice, color: d.color || _drawDefaults.color,
            lineWidth: d.lineWidth || 2, lineStyle: d.lineStyle || 0,
            axisLabelVisible: d.showPriceLabel !== false,
            title: d.title || '',
        });
        ds.priceLines[drawIdx] = { seriesId: mainKey, priceLine: newPl };
    }
}

// ---------------------------------------------------------------------------
// Indicators Panel
// ---------------------------------------------------------------------------
var _indicatorsOverlay = null;
var _indicatorsOverlayChartId = null;
var _activeIndicators = {};  // { seriesId: { name, period, chartId } }

var _INDICATOR_CATALOG = [
    { key: 'average-price', name: 'Average Price', fullName: 'Average Price', category: 'Lightweight Examples', defaultPeriod: 0 },
    { key: 'correlation', name: 'Correlation', fullName: 'Correlation', category: 'Lightweight Examples', defaultPeriod: 20, requiresSecondary: true, subplot: true },
    { key: 'median-price', name: 'Median Price', fullName: 'Median Price', category: 'Lightweight Examples', defaultPeriod: 0 },
    { key: 'momentum', name: 'Momentum', fullName: 'Momentum', category: 'Lightweight Examples', defaultPeriod: 10, subplot: true },
    { key: 'moving-average-ex', name: 'Moving Average', fullName: 'Moving Average', category: 'Moving Averages', defaultPeriod: 9 },
    { key: 'percent-change', name: 'Percent Change', fullName: 'Percent Change', category: 'Lightweight Examples', defaultPeriod: 0, subplot: true },
    { key: 'product', name: 'Product', fullName: 'Product', category: 'Lightweight Examples', defaultPeriod: 0, requiresSecondary: true, subplot: true },
    { key: 'ratio', name: 'Ratio', fullName: 'Ratio', category: 'Lightweight Examples', defaultPeriod: 0, requiresSecondary: true, subplot: true },
    { key: 'spread', name: 'Spread', fullName: 'Spread', category: 'Lightweight Examples', defaultPeriod: 0, requiresSecondary: true, subplot: true },
    { key: 'sum', name: 'Sum', fullName: 'Sum', category: 'Lightweight Examples', defaultPeriod: 0, requiresSecondary: true, subplot: true },
    { key: 'weighted-close', name: 'Weighted Close', fullName: 'Weighted Close', category: 'Lightweight Examples', defaultPeriod: 0 },

    // Moving-average variants are reachable from the single "Moving
    // Average" entry above — open the settings dialog and pick a Type
    // (SMA / EMA / WMA / HMA / VWMA) and Length.
    { name: 'Ichimoku Cloud', fullName: 'Ichimoku Cloud', category: 'Moving Averages', defaultPeriod: 26 },
    { name: 'Bollinger Bands', fullName: 'Bollinger Bands', category: 'Volatility', defaultPeriod: 20 },
    { name: 'Keltner Channels', fullName: 'Keltner Channels', category: 'Volatility', defaultPeriod: 20 },
    { name: 'ATR', fullName: 'Average True Range', category: 'Volatility', defaultPeriod: 14 },
    { name: 'Historical Volatility', fullName: 'Historical Volatility', category: 'Volatility', defaultPeriod: 10, subplot: true },
    { name: 'Parabolic SAR', fullName: 'Parabolic Stop and Reverse', category: 'Trend', defaultPeriod: 0 },
    { name: 'RSI', fullName: 'Relative Strength Index', category: 'Momentum', defaultPeriod: 14, subplot: true },
    { name: 'MACD', fullName: 'Moving Average Convergence/Divergence', category: 'Momentum', defaultPeriod: 12, subplot: true },
    { name: 'Stochastic', fullName: 'Stochastic Oscillator', category: 'Momentum', defaultPeriod: 14, subplot: true },
    { name: 'Williams %R', fullName: 'Williams %R', category: 'Momentum', defaultPeriod: 14, subplot: true },
    { name: 'CCI', fullName: 'Commodity Channel Index', category: 'Momentum', defaultPeriod: 20, subplot: true },
    { name: 'ADX', fullName: 'Average Directional Index', category: 'Momentum', defaultPeriod: 14, subplot: true },
    { name: 'Aroon', fullName: 'Aroon Up/Down', category: 'Momentum', defaultPeriod: 14, subplot: true },
    { name: 'VWAP', fullName: 'Volume Weighted Average Price', category: 'Volume', defaultPeriod: 0 },
    { name: 'Volume SMA', fullName: 'Volume Simple Moving Average', category: 'Volume', defaultPeriod: 20 },
    { name: 'Accumulation/Distribution', fullName: 'Accumulation / Distribution Line', category: 'Volume', defaultPeriod: 0, subplot: true },
    { key: 'volume-profile-fixed', name: 'Volume Profile Fixed Range', fullName: 'Volume Profile (Fixed Range)', category: 'Volume', defaultPeriod: 24, primitive: true },
    { key: 'volume-profile-visible', name: 'Volume Profile Visible Range', fullName: 'Volume Profile (Visible Range)', category: 'Volume', defaultPeriod: 24, primitive: true },
];

// ---- Indicator computation functions ----
