function _computeVWAP(data) {
    var result = [];
    var cumVol = 0, cumTP = 0;
    for (var i = 0; i < data.length; i++) {
        var h = data[i].high || data[i].close || data[i].value || 0;
        var l = data[i].low || data[i].close || data[i].value || 0;
        var c = data[i].close !== undefined ? data[i].close : data[i].value || 0;
        var v = data[i].volume || 1;
        var tp = (h + l + c) / 3;
        cumTP += tp * v;
        cumVol += v;
        result.push({ time: data[i].time, value: cumVol > 0 ? cumTP / cumVol : tp });
    }
    return result;
}

// ---------------------------------------------------------------------------
// Additional built-in indicators (textbook formulas)
// ---------------------------------------------------------------------------

/** Volume-Weighted Moving Average: sum(src*vol) / sum(vol) over a window. */
function _computeVWMA(data, period, source) {
    source = source || 'close';
    var result = [];
    for (var i = 0; i < data.length; i++) {
        if (i < period - 1) { result.push({ time: data[i].time }); continue; }
        var numer = 0, denom = 0;
        for (var j = i - period + 1; j <= i; j++) {
            var c = _tvIndicatorValue(data[j], source);
            var v = data[j].volume || 0;
            numer += c * v;
            denom += v;
        }
        result.push({ time: data[i].time, value: denom > 0 ? numer / denom : undefined });
    }
    return result;
}

/** Hull Moving Average: WMA(2 * WMA(src, n/2) - WMA(src, n), sqrt(n)). */
function _computeHMA(data, period, source) {
    source = source || 'close';
    var half = Math.max(1, Math.floor(period / 2));
    var sqrtN = Math.max(1, Math.floor(Math.sqrt(period)));
    var srcSeries = data.map(function(p) { return { time: p.time, value: _tvIndicatorValue(p, source) }; });
    var wmaHalf = _computeWMA(srcSeries, half, 'value');
    var wmaFull = _computeWMA(srcSeries, period, 'value');
    var diff = [];
    for (var i = 0; i < data.length; i++) {
        var a = wmaHalf[i].value;
        var b = wmaFull[i].value;
        diff.push({
            time: data[i].time,
            value: (a !== undefined && b !== undefined) ? (2 * a - b) : undefined,
        });
    }
    return _computeWMA(diff, sqrtN, 'value');
}

/** Commodity Channel Index: (Source - SMA(Source, n)) / (0.015 * meanDev(Source, n)). */
function _computeCCI(data, period, source) {
    source = source || 'hlc3';   // TradingView default for CCI
    var tp = data.map(function(p) { return { time: p.time, value: _tvIndicatorValue(p, source) }; });
    var sma = _computeSMA(tp, period, 'value');
    var result = [];
    for (var k = 0; k < tp.length; k++) {
        if (k < period - 1 || sma[k].value === undefined) {
            result.push({ time: tp[k].time });
            continue;
        }
        var mean = sma[k].value;
        var dev = 0;
        for (var j = k - period + 1; j <= k; j++) {
            dev += Math.abs(tp[j].value - mean);
        }
        dev /= period;
        result.push({
            time: tp[k].time,
            value: dev > 0 ? (tp[k].value - mean) / (0.015 * dev) : 0,
        });
    }
    return result;
}

/** Williams %R: -100 * (highestHigh - source) / (highestHigh - lowestLow). */
function _computeWilliamsR(data, period, source) {
    source = source || 'close';
    var result = [];
    for (var i = 0; i < data.length; i++) {
        if (i < period - 1) { result.push({ time: data[i].time }); continue; }
        var hh = -Infinity, ll = Infinity;
        for (var j = i - period + 1; j <= i; j++) {
            var h = data[j].high !== undefined ? data[j].high : data[j].close;
            var l = data[j].low !== undefined ? data[j].low : data[j].close;
            if (h > hh) hh = h;
            if (l < ll) ll = l;
        }
        var c = _tvIndicatorValue(data[i], source);
        var range = hh - ll;
        result.push({
            time: data[i].time,
            value: range > 0 ? -100 * (hh - c) / range : 0,
        });
    }
    return result;
}

/**
 * Stochastic Oscillator with TradingView's three-length signature:
 *   kLength    "%K Length"     default 14   raw %K window
 *   kSmoothing "%K Smoothing"  default 1    SMA over raw %K (1 = none)
 *   dSmoothing "%D Smoothing"  default 3    SMA over smoothed %K
 */
function _computeStochastic(data, kLength, kSmoothing, dSmoothing) {
    var kRaw = [];
    for (var i = 0; i < data.length; i++) {
        if (i < kLength - 1) { kRaw.push({ time: data[i].time }); continue; }
        var hh = -Infinity, ll = Infinity;
        for (var j = i - kLength + 1; j <= i; j++) {
            var h = data[j].high !== undefined ? data[j].high : data[j].close;
            var l = data[j].low !== undefined ? data[j].low : data[j].close;
            if (h > hh) hh = h;
            if (l < ll) ll = l;
        }
        var c = data[i].close !== undefined ? data[i].close : data[i].value || 0;
        var range = hh - ll;
        kRaw.push({ time: data[i].time, value: range > 0 ? 100 * (c - ll) / range : 50 });
    }
    var k = (kSmoothing && kSmoothing > 1) ? _computeSMA(kRaw, kSmoothing, 'value') : kRaw;
    var d = _computeSMA(k, dSmoothing || 3, 'value');
    return { k: k, d: d };
}

/** Aroon Up and Down: 100 * (period - barsSince {high|low}) / period. */
function _computeAroon(data, period) {
    var up = [], down = [];
    for (var i = 0; i < data.length; i++) {
        if (i < period) {
            up.push({ time: data[i].time });
            down.push({ time: data[i].time });
            continue;
        }
        var hh = -Infinity, ll = Infinity;
        var hIdx = i, lIdx = i;
        for (var j = i - period; j <= i; j++) {
            var h = data[j].high !== undefined ? data[j].high : data[j].close;
            var l = data[j].low !== undefined ? data[j].low : data[j].close;
            if (h >= hh) { hh = h; hIdx = j; }
            if (l <= ll) { ll = l; lIdx = j; }
        }
        up.push({ time: data[i].time, value: 100 * (period - (i - hIdx)) / period });
        down.push({ time: data[i].time, value: 100 * (period - (i - lIdx)) / period });
    }
    return { up: up, down: down };
}

/**
 * Average Directional Index (ADX) — TradingView's two-length form:
 *   diLength       Lookback for +DI / -DI                 default 14
 *   adxSmoothing   Lookback for the ADX itself (DX MA)    default 14
 *
 * Back-compat: if only one arg is passed, both lengths use it.
 */
function _computeADX(data, diLength, adxSmoothing) {
    if (adxSmoothing === undefined) adxSmoothing = diLength;
    var period = diLength;
    var plusDM = [], minusDM = [], tr = [];
    for (var i = 0; i < data.length; i++) {
        if (i === 0) { plusDM.push(0); minusDM.push(0); tr.push(0); continue; }
        var h = data[i].high !== undefined ? data[i].high : data[i].close;
        var l = data[i].low !== undefined ? data[i].low : data[i].close;
        var pH = data[i - 1].high !== undefined ? data[i - 1].high : data[i - 1].close;
        var pL = data[i - 1].low !== undefined ? data[i - 1].low : data[i - 1].close;
        var pC = data[i - 1].close !== undefined ? data[i - 1].close : data[i - 1].value || 0;
        var upMove = h - pH;
        var downMove = pL - l;
        plusDM.push(upMove > downMove && upMove > 0 ? upMove : 0);
        minusDM.push(downMove > upMove && downMove > 0 ? downMove : 0);
        tr.push(Math.max(h - l, Math.abs(h - pC), Math.abs(l - pC)));
    }

    // Wilder smoothing (same formula as RMA / ATR's recursive smoothing)
    function wilder(arr) {
        var out = new Array(arr.length);
        var sum = 0;
        for (var i = 0; i < arr.length; i++) {
            if (i < period) { sum += arr[i]; out[i] = undefined; if (i === period - 1) out[i] = sum; continue; }
            out[i] = out[i - 1] - out[i - 1] / period + arr[i];
        }
        return out;
    }

    var trS = wilder(tr);
    var plusS = wilder(plusDM);
    var minusS = wilder(minusDM);

    var plusDI = [], minusDI = [], dx = [];
    for (var k = 0; k < data.length; k++) {
        if (trS[k] === undefined || trS[k] === 0) {
            plusDI.push({ time: data[k].time });
            minusDI.push({ time: data[k].time });
            dx.push(undefined);
            continue;
        }
        var pdi = 100 * plusS[k] / trS[k];
        var mdi = 100 * minusS[k] / trS[k];
        plusDI.push({ time: data[k].time, value: pdi });
        minusDI.push({ time: data[k].time, value: mdi });
        dx.push(pdi + mdi > 0 ? 100 * Math.abs(pdi - mdi) / (pdi + mdi) : 0);
    }

    // ADX = Wilder smoothing of DX over adxSmoothing, starting once we
    // have `adxSmoothing` valid DX values.
    var adx = [];
    var adxVal = null;
    var dxSum = 0, dxCount = 0, dxStart = -1;
    for (var m = 0; m < data.length; m++) {
        if (dx[m] === undefined) { adx.push({ time: data[m].time }); continue; }
        if (dxStart < 0) dxStart = m;
        if (m - dxStart < adxSmoothing) {
            dxSum += dx[m];
            dxCount += 1;
            if (dxCount === adxSmoothing) {
                adxVal = dxSum / adxSmoothing;
                adx.push({ time: data[m].time, value: adxVal });
            } else {
                adx.push({ time: data[m].time });
            }
        } else {
            adxVal = (adxVal * (adxSmoothing - 1) + dx[m]) / adxSmoothing;
            adx.push({ time: data[m].time, value: adxVal });
        }
    }

    return { adx: adx, plusDI: plusDI, minusDI: minusDI };
}

/** MACD: MA(fast) - MA(slow), signal MA of MACD, histogram = MACD - signal. */
function _computeMACD(data, fast, slow, signal, source, oscMaType, signalMaType) {
    source = source || 'close';
    oscMaType = oscMaType || 'EMA';
    signalMaType = signalMaType || 'EMA';

    var srcSeries = data.map(function(p) {
        return { time: p.time, value: _tvIndicatorValue(p, source) };
    });
    function maFn(t) {
        return t === 'SMA' ? _computeSMA : t === 'WMA' ? _computeWMA : _computeEMA;
    }

    var maFast = maFn(oscMaType)(srcSeries, fast, 'value');
    var maSlow = maFn(oscMaType)(srcSeries, slow, 'value');
    var macd = [];
    for (var i = 0; i < data.length; i++) {
        var f = maFast[i].value;
        var s = maSlow[i].value;
        macd.push({
            time: data[i].time,
            value: (f !== undefined && s !== undefined) ? f - s : undefined,
        });
    }
    var sig = maFn(signalMaType)(macd, signal, 'value');
    var hist = [];
    for (var k = 0; k < data.length; k++) {
        var mv = macd[k].value;
        var sv = sig[k].value;
        hist.push({
            time: data[k].time,
            value: (mv !== undefined && sv !== undefined) ? mv - sv : undefined,
        });
    }
    return { macd: macd, signal: sig, histogram: hist };
}

/** Accumulation/Distribution: cumulative CLV * volume. */
function _computeAccumulationDistribution(data) {
    var out = [];
    var ad = 0;
    for (var i = 0; i < data.length; i++) {
        var h = data[i].high !== undefined ? data[i].high : data[i].close;
        var l = data[i].low !== undefined ? data[i].low : data[i].close;
        var c = data[i].close !== undefined ? data[i].close : data[i].value || 0;
        var v = data[i].volume || 0;
        var range = h - l;
        var clv = range > 0 ? ((c - l) - (h - c)) / range : 0;
        ad += clv * v;
        out.push({ time: data[i].time, value: ad });
    }
    return out;
}

/** Historical Volatility: stdev of log returns * sqrt(annualizationFactor) * 100. */
function _computeHistoricalVolatility(data, period, annualization) {
    var ann = annualization || 252;
    var returns = [];
    for (var i = 0; i < data.length; i++) {
        if (i === 0) { returns.push({ time: data[i].time, value: undefined }); continue; }
        var pC = data[i - 1].close !== undefined ? data[i - 1].close : data[i - 1].value || 0;
        var c = data[i].close !== undefined ? data[i].close : data[i].value || 0;
        if (pC > 0 && c > 0) {
            returns.push({ time: data[i].time, value: Math.log(c / pC) });
        } else {
            returns.push({ time: data[i].time, value: undefined });
        }
    }
    var out = [];
    for (var k = 0; k < data.length; k++) {
        if (k < period) { out.push({ time: data[k].time }); continue; }
        var sum = 0, count = 0;
        for (var j = k - period + 1; j <= k; j++) {
            if (returns[j].value !== undefined) { sum += returns[j].value; count += 1; }
        }
        if (count === 0) { out.push({ time: data[k].time }); continue; }
        var mean = sum / count;
        var sq = 0;
        for (var jj = k - period + 1; jj <= k; jj++) {
            if (returns[jj].value !== undefined) sq += (returns[jj].value - mean) * (returns[jj].value - mean);
        }
        var stdev = Math.sqrt(sq / count);
        out.push({ time: data[k].time, value: stdev * Math.sqrt(ann) * 100 });
    }
    return out;
}

/** Keltner Channels: EMA(n) ± multiplier * ATR(n). */
function _computeKeltnerChannels(data, period, multiplier, maType) {
    multiplier = multiplier || 2;
    maType = maType || 'EMA';
    var maFn = maType === 'SMA' ? _computeSMA : (maType === 'WMA' ? _computeWMA : _computeEMA);
    var mid = maFn(data, period);
    var atr = _computeATR(data, period);
    var upper = [], lower = [];
    for (var i = 0; i < data.length; i++) {
        var m = mid[i].value;
        var a = atr[i].value;
        if (m === undefined || a === undefined) {
            upper.push({ time: data[i].time });
            lower.push({ time: data[i].time });
            continue;
        }
        upper.push({ time: data[i].time, value: m + multiplier * a });
        lower.push({ time: data[i].time, value: m - multiplier * a });
    }
    return { middle: mid, upper: upper, lower: lower };
}

/**
 * Ichimoku Kinko Hyo — five-line indicator with TradingView's parameter names:
 *
 *   conversionP   "Conversion Line Periods"  (Tenkan-sen)        default 9
 *   baseP         "Base Line Periods"        (Kijun-sen)         default 26
 *   leadingSpanP  "Leading Span Periods"     (Senkou Span B)     default 52
 *   laggingP      "Lagging Span Periods"     (Chikou shift back) default 26
 *   leadingShiftP "Leading Shift Periods"    (Senkou A/B fwd)    default 26
 *
 * Returned arrays are ready for ``setData``.  Senkou Span A/B are
 * forward-shifted onto synthesised future timestamps so the cloud
 * actually projects into the future like TradingView's real version.
 */
function _computeIchimoku(data, conversionP, baseP, leadingSpanP, laggingP, leadingShiftP) {
    // Back-compat: old callers pass (data, tenkanP, kijunP, senkouBP).
    if (laggingP === undefined) laggingP = baseP;
    if (leadingShiftP === undefined) leadingShiftP = baseP;
    function highestHigh(lo, hi) {
        var best = -Infinity;
        for (var i = lo; i <= hi; i++) {
            var h = data[i].high !== undefined ? data[i].high : data[i].close;
            if (h > best) best = h;
        }
        return best;
    }
    function lowestLow(lo, hi) {
        var best = Infinity;
        for (var i = lo; i <= hi; i++) {
            var l = data[i].low !== undefined ? data[i].low : data[i].close;
            if (l < best) best = l;
        }
        return best;
    }
    function timeToNum(t) {
        if (typeof t === 'number') return t;
        if (typeof t === 'object' && t && 'year' in t) {
            // Business day { year, month, day }
            return Date.UTC(t.year, (t.month || 1) - 1, t.day || 1) / 1000;
        }
        var n = Number(t);
        return isFinite(n) ? n : 0;
    }

    var tenkan = [], kijun = [];
    for (var i = 0; i < data.length; i++) {
        if (i >= conversionP - 1) {
            tenkan.push({ time: data[i].time, value: (highestHigh(i - conversionP + 1, i) + lowestLow(i - conversionP + 1, i)) / 2 });
        } else {
            tenkan.push({ time: data[i].time });
        }
        if (i >= baseP - 1) {
            kijun.push({ time: data[i].time, value: (highestHigh(i - baseP + 1, i) + lowestLow(i - baseP + 1, i)) / 2 });
        } else {
            kijun.push({ time: data[i].time });
        }
    }

    // Median bar interval — robust against weekends / holidays in OHLCV
    // feeds because we sort the deltas and take the middle one.
    var deltas = [];
    for (var d = 1; d < data.length; d++) {
        var dt = timeToNum(data[d].time) - timeToNum(data[d - 1].time);
        if (dt > 0) deltas.push(dt);
    }
    deltas.sort(function(a, b) { return a - b; });
    var barSeconds = deltas.length ? deltas[Math.floor(deltas.length / 2)] : 86400;

    // Future timestamps for the forward-shifted cloud.  We need
    // leadingShiftP points past the last bar; reuse the median
    // interval for spacing.
    var futureTimes = [];
    var lastTime = timeToNum(data[data.length - 1].time);
    for (var f = 1; f <= leadingShiftP; f++) {
        futureTimes.push(lastTime + barSeconds * f);
    }

    // Senkou Span A: (tenkan + kijun) / 2 at index i, plotted at
    // time[i + leadingShiftP].  Senkou Span B: midpoint of
    // leadingSpanP bars at index i, also forward-shifted.
    var spanA = [], spanB = [];
    function shiftedTime(srcIdx) {
        var dst = srcIdx + leadingShiftP;
        if (dst < data.length) return data[dst].time;
        var futIdx = dst - data.length;
        if (futIdx < futureTimes.length) return futureTimes[futIdx];
        return null;
    }

    for (var k = 0; k < data.length; k++) {
        var t = shiftedTime(k);
        if (t === null) continue;
        if (tenkan[k].value !== undefined && kijun[k].value !== undefined) {
            spanA.push({ time: t, value: (tenkan[k].value + kijun[k].value) / 2 });
        } else {
            spanA.push({ time: t });
        }
        if (k >= leadingSpanP - 1) {
            spanB.push({ time: t, value: (highestHigh(k - leadingSpanP + 1, k) + lowestLow(k - leadingSpanP + 1, k)) / 2 });
        } else {
            spanB.push({ time: t });
        }
    }

    // Chikou Span: current close plotted laggingP bars in the PAST.
    // At time[m], display value = close[m + laggingP].
    var chikou = [];
    for (var m = 0; m < data.length; m++) {
        var src = m + laggingP;
        if (src < data.length) {
            var c = data[src].close !== undefined ? data[src].close : data[src].value || 0;
            chikou.push({ time: data[m].time, value: c });
        } else {
            chikou.push({ time: data[m].time });
        }
    }

    return {
        tenkan: tenkan,
        kijun: kijun,
        spanA: spanA,
        spanB: spanB,
        chikou: chikou,
        futureTimes: futureTimes,
    };
}

/** Parabolic SAR: trailing stop flipped when price crosses, with acceleration. */
function _computeParabolicSAR(data, step, maxStep) {
    step = step || 0.02;
    maxStep = maxStep || 0.2;
    if (data.length < 2) return data.map(function(d) { return { time: d.time }; });

    var out = [];
    var uptrend = true;
    var af = step;
    var ep = data[0].high !== undefined ? data[0].high : data[0].close;
    var sar = data[0].low !== undefined ? data[0].low : data[0].close;

    out.push({ time: data[0].time });  // undefined — need 2 bars to seed

    // Decide initial trend from first two bars
    var c0 = data[0].close !== undefined ? data[0].close : data[0].value || 0;
    var c1 = data[1].close !== undefined ? data[1].close : data[1].value || 0;
    uptrend = c1 >= c0;
    if (uptrend) {
        sar = data[0].low !== undefined ? data[0].low : c0;
        ep = data[1].high !== undefined ? data[1].high : c1;
    } else {
        sar = data[0].high !== undefined ? data[0].high : c0;
        ep = data[1].low !== undefined ? data[1].low : c1;
    }
    out.push({ time: data[1].time, value: sar });

    for (var i = 2; i < data.length; i++) {
        var h = data[i].high !== undefined ? data[i].high : data[i].close;
        var l = data[i].low !== undefined ? data[i].low : data[i].close;
        var prevHigh = data[i - 1].high !== undefined ? data[i - 1].high : data[i - 1].close;
        var prevLow = data[i - 1].low !== undefined ? data[i - 1].low : data[i - 1].close;

        sar = sar + af * (ep - sar);

        if (uptrend) {
            // SAR can't exceed prior two lows
            sar = Math.min(sar, prevLow, data[i - 2].low !== undefined ? data[i - 2].low : data[i - 2].close);
            if (l < sar) {
                // Flip to downtrend
                uptrend = false;
                sar = ep;
                ep = l;
                af = step;
            } else {
                if (h > ep) {
                    ep = h;
                    af = Math.min(af + step, maxStep);
                }
            }
        } else {
            sar = Math.max(sar, prevHigh, data[i - 2].high !== undefined ? data[i - 2].high : data[i - 2].close);
            if (h > sar) {
                uptrend = true;
                sar = ep;
                ep = h;
                af = step;
            } else {
                if (l < ep) {
                    ep = l;
                    af = Math.min(af + step, maxStep);
                }
            }
        }
        out.push({ time: data[i].time, value: sar });
    }
    return out;
}
