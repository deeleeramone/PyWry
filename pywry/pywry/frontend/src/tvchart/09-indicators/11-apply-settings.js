function _tvApplyIndicatorSettings(seriesId, newSettings) {
    var info = _activeIndicators[seriesId];
    if (!info) return;
    var entry = window.__PYWRY_TVCHARTS__[info.chartId];
    if (!entry) return;
    var rawData = _tvSeriesRawData(entry, info.sourceSeriesId || 'main');
    var periodChanged = !!(newSettings.period && info.period > 0 && newSettings.period !== info.period);
    var multChanged = !!(info.group && newSettings.multiplier !== (info.multiplier || 2));
    var sourceChanged = !!(newSettings.source && newSettings.source !== info.source);
    var methodChanged = !!(newSettings.method && newSettings.method !== info.method);
    var maTypeChanged = !!(newSettings.maType && newSettings.maType !== (info.maType || 'SMA'));
    var offsetChanged = (newSettings.offset !== undefined && newSettings.offset !== (info.offset || 0));
    var primarySourceChanged = !!(newSettings.primarySource && newSettings.primarySource !== info.primarySource);
    var secondarySourceChanged = !!(newSettings.secondarySource && newSettings.secondarySource !== info.secondarySource);
    // New-indicator change detection: any compound-length parameter shift
    // also triggers the recompute branch below.
    var fastChanged = !!(newSettings.fast && newSettings.fast !== info.fast);
    var slowChanged = !!(newSettings.slow && newSettings.slow !== info.slow);
    var signalChanged = !!(newSettings.signal && newSettings.signal !== info.signal);
    var kPeriodChanged = !!(newSettings.kPeriod && newSettings.kPeriod !== info.kPeriod);
    var dPeriodChanged = !!(newSettings.dPeriod && newSettings.dPeriod !== info.dPeriod);
    var conversionChanged = !!(newSettings.conversionPeriod && newSettings.conversionPeriod !== info.conversionPeriod);
    var baseChanged = !!(newSettings.basePeriod && newSettings.basePeriod !== info.basePeriod);
    var leadingSpanChanged = !!(newSettings.leadingSpanPeriod && newSettings.leadingSpanPeriod !== info.leadingSpanPeriod);
    var laggingChanged = !!(newSettings.laggingPeriod && newSettings.laggingPeriod !== info.laggingPeriod);
    var leadingShiftChanged = !!(newSettings.leadingShiftPeriod && newSettings.leadingShiftPeriod !== info.leadingShiftPeriod);
    // Back-compat aliases (older callers might still use the original names)
    var tenkanChanged = !!(newSettings.tenkan && newSettings.tenkan !== info.tenkan);
    var kijunChanged = !!(newSettings.kijun && newSettings.kijun !== info.kijun);
    var senkouBChanged = !!(newSettings.senkouB && newSettings.senkouB !== info.senkouB);
    var stepChanged = (newSettings.step !== undefined && newSettings.step !== info.step);
    var maxStepChanged = (newSettings.maxStep !== undefined && newSettings.maxStep !== info.maxStep);
    var annualizationChanged = !!(newSettings.annualization && newSettings.annualization !== info.annualization);
    var kSmoothingChanged = !!(newSettings.kSmoothing && newSettings.kSmoothing !== info.kSmoothing);
    var adxSmoothingChanged = !!(newSettings.adxSmoothing && newSettings.adxSmoothing !== info.adxSmoothing);
    var diLengthChanged = !!(newSettings.diLength && newSettings.diLength !== info.diLength);
    var macdSourceChanged = !!(newSettings.macdSource && newSettings.macdSource !== info.macdSource);
    var oscMaTypeChanged = !!(newSettings.oscMaType && newSettings.oscMaType !== info.oscMaType);
    var signalMaTypeChanged = !!(newSettings.signalMaType && newSettings.signalMaType !== info.signalMaType);
    var compoundChanged = fastChanged || slowChanged || signalChanged
        || kPeriodChanged || dPeriodChanged || kSmoothingChanged
        || adxSmoothingChanged || diLengthChanged
        || macdSourceChanged || oscMaTypeChanged || signalMaTypeChanged
        || tenkanChanged || kijunChanged || senkouBChanged
        || conversionChanged || baseChanged || leadingSpanChanged
        || laggingChanged || leadingShiftChanged
        || stepChanged || maxStepChanged || annualizationChanged;
    var type = info.type || info.name;

    // Apply per-plot styles
    var styleSids = [];
    if (info.group) {
        var allKeys = Object.keys(_activeIndicators);
        for (var k = 0; k < allKeys.length; k++) { if (_activeIndicators[allKeys[k]].group === info.group) styleSids.push(allKeys[k]); }
    } else { styleSids = [seriesId]; }
    for (var si = 0; si < styleSids.length; si++) {
        var ss = entry.seriesMap[styleSids[si]];
        var plotDraft = newSettings.plotStyles && newSettings.plotStyles[styleSids[si]];
        var isBaselineSeries = !!(_activeIndicators[styleSids[si]] && _activeIndicators[styleSids[si]].isBaseline);
        if (plotDraft) {
            var opts;
            if (isBaselineSeries) {
                opts = { topLineColor: plotDraft.color, bottomLineColor: plotDraft.color, lineWidth: plotDraft.lineWidth, lineStyle: plotDraft.lineStyle || 0 };
            } else {
                opts = { color: plotDraft.color, lineWidth: plotDraft.lineWidth, lineStyle: plotDraft.lineStyle || 0 };
            }
            if (plotDraft.visible === false) opts.visible = false;
            else opts.visible = true;
            if (ss) { try { ss.applyOptions(opts); } catch(e) {} }
            if (_activeIndicators[styleSids[si]]) {
                _activeIndicators[styleSids[si]].color = plotDraft.color;
                _activeIndicators[styleSids[si]].lineWidth = plotDraft.lineWidth;
                _activeIndicators[styleSids[si]].lineStyle = plotDraft.lineStyle;
                _activeIndicators[styleSids[si]].visible = plotDraft.visible;
            }
        } else {
            // Fallback to draft top-level color/lineWidth
            if (isBaselineSeries) {
                if (ss) { try { ss.applyOptions({ topLineColor: newSettings.color, bottomLineColor: newSettings.color, lineWidth: newSettings.lineWidth }); } catch(e) {} }
            } else {
                if (ss) { try { ss.applyOptions({ color: newSettings.color, lineWidth: newSettings.lineWidth }); } catch(e) {} }
            }
            if (_activeIndicators[styleSids[si]]) { _activeIndicators[styleSids[si]].color = newSettings.color; _activeIndicators[styleSids[si]].lineWidth = newSettings.lineWidth; }
        }
    }

    // Apply baseline fill settings for binary indicators
    if (info.isBaseline) {
        var bSeries = entry.seriesMap[seriesId];
        if (bSeries) {
            var fillOpts = {};
            if (newSettings.showPositiveFill) {
                var pc = newSettings.positiveFillColor || '#26a69a';
                var pOp = _tvClamp(_tvToNumber(newSettings.positiveFillOpacity, 100), 0, 100) / 100;
                fillOpts.topFillColor1 = _tvHexToRgba(pc, 0.28 * pOp);
                fillOpts.topFillColor2 = _tvHexToRgba(pc, 0.05 * pOp);
            } else {
                fillOpts.topFillColor1 = 'transparent';
                fillOpts.topFillColor2 = 'transparent';
            }
            if (newSettings.showNegativeFill) {
                var nc = newSettings.negativeFillColor || '#ef5350';
                var nOp = _tvClamp(_tvToNumber(newSettings.negativeFillOpacity, 100), 0, 100) / 100;
                fillOpts.bottomFillColor1 = _tvHexToRgba(nc, 0.05 * nOp);
                fillOpts.bottomFillColor2 = _tvHexToRgba(nc, 0.28 * nOp);
            } else {
                fillOpts.bottomFillColor1 = 'transparent';
                fillOpts.bottomFillColor2 = 'transparent';
            }
            try { bSeries.applyOptions(fillOpts); } catch(e) {}
        }
        info.showPositiveFill = newSettings.showPositiveFill;
        info.positiveFillColor = newSettings.positiveFillColor;
        info.positiveFillOpacity = newSettings.positiveFillOpacity;
        info.showNegativeFill = newSettings.showNegativeFill;
        info.negativeFillColor = newSettings.negativeFillColor;
        info.negativeFillOpacity = newSettings.negativeFillOpacity;
        info.precision = newSettings.precision;
        info.labelsOnPriceScale = newSettings.labelsOnPriceScale;
        info.valuesInStatusLine = newSettings.valuesInStatusLine;
        info.inputsInStatusLine = newSettings.inputsInStatusLine;
        // Apply precision
        if (bSeries && newSettings.precision && newSettings.precision !== 'default') {
            try { bSeries.applyOptions({ priceFormat: { type: 'price', precision: Number(newSettings.precision), minMove: Math.pow(10, -Number(newSettings.precision)) } }); } catch(e) {}
        }
        // Apply labels on price scale
        if (bSeries) {
            try { bSeries.applyOptions({ lastValueVisible: newSettings.labelsOnPriceScale !== false }); } catch(e) {}
        }
    }

    // Store RSI-specific settings
    if (newSettings.showUpperLimit !== undefined) {
        info.showUpperLimit = newSettings.showUpperLimit;
        info.upperLimitValue = newSettings.upperLimitValue;
        info.upperLimitColor = newSettings.upperLimitColor;
        info.showLowerLimit = newSettings.showLowerLimit;
        info.lowerLimitValue = newSettings.lowerLimitValue;
        info.lowerLimitColor = newSettings.lowerLimitColor;
        info.showMiddleLimit = newSettings.showMiddleLimit;
        info.middleLimitValue = newSettings.middleLimitValue;
        info.middleLimitColor = newSettings.middleLimitColor;
        info.showBackground = newSettings.showBackground;
        info.bgColor = newSettings.bgColor;
        info.bgOpacity = newSettings.bgOpacity;
    }
    // Store smoothing settings
    if (newSettings.smoothingLine !== undefined) info.smoothingLine = newSettings.smoothingLine;
    if (newSettings.smoothingLength !== undefined) info.smoothingLength = newSettings.smoothingLength;
    // Store BB-specific settings (propagate to all group members)
    if (type === 'bollinger-bands' && info.group) {
        var bbKeys = Object.keys(_activeIndicators);
        for (var bk = 0; bk < bbKeys.length; bk++) {
            if (_activeIndicators[bbKeys[bk]].group !== info.group) continue;
            _activeIndicators[bbKeys[bk]].showBandFill = newSettings.showBandFill;
            _activeIndicators[bbKeys[bk]].bandFillColor = newSettings.bandFillColor;
            _activeIndicators[bbKeys[bk]].bandFillOpacity = newSettings.bandFillOpacity;
            _activeIndicators[bbKeys[bk]].precision = newSettings.precision;
            _activeIndicators[bbKeys[bk]].labelsOnPriceScale = newSettings.labelsOnPriceScale;
            _activeIndicators[bbKeys[bk]].valuesInStatusLine = newSettings.valuesInStatusLine;
            _activeIndicators[bbKeys[bk]].inputsInStatusLine = newSettings.inputsInStatusLine;
        }
    }
    // Store visibility
    if (newSettings.visibility) info.visibility = newSettings.visibility;

    // Universal OUTPUT VALUES — propagate Precision / Labels on price scale
    // / Values in status line to every series in the indicator's group (or
    // just this one if there's no group).  TradingView shows these on
    // every Style tab, so they need to apply uniformly.
    if (newSettings.precision !== undefined
        || newSettings.labelsOnPriceScale !== undefined
        || newSettings.valuesInStatusLine !== undefined
        || newSettings.inputsInStatusLine !== undefined) {
        var ovSids = info.group
            ? Object.keys(_activeIndicators).filter(function(k) {
                return _activeIndicators[k].group === info.group;
            })
            : [seriesId];
        ovSids.forEach(function(sid) {
            var ai = _activeIndicators[sid];
            if (!ai) return;
            if (newSettings.precision !== undefined) ai.precision = newSettings.precision;
            if (newSettings.labelsOnPriceScale !== undefined) ai.labelsOnPriceScale = newSettings.labelsOnPriceScale;
            if (newSettings.valuesInStatusLine !== undefined) ai.valuesInStatusLine = newSettings.valuesInStatusLine;
            if (newSettings.inputsInStatusLine !== undefined) ai.inputsInStatusLine = newSettings.inputsInStatusLine;
            var ser = entry.seriesMap[sid];
            if (!ser) return;
            try {
                if (newSettings.precision !== undefined) {
                    if (newSettings.precision === 'default') {
                        ser.applyOptions({ priceFormat: { type: 'price' } });
                    } else {
                        var p = Number(newSettings.precision);
                        ser.applyOptions({ priceFormat: { type: 'price', precision: p, minMove: Math.pow(10, -p) } });
                    }
                }
                if (newSettings.labelsOnPriceScale !== undefined) {
                    ser.applyOptions({ lastValueVisible: newSettings.labelsOnPriceScale !== false });
                }
            } catch (e) {}
        });
    }

    // Recompute if period / multiplier / source / method / maType / offset
    // changed, or if any compound-length parameter on a new indicator shifted.
    if ((periodChanged || multChanged || sourceChanged || methodChanged || maTypeChanged || offsetChanged || primarySourceChanged || secondarySourceChanged || compoundChanged) && rawData) {
        var baseName = info.name.replace(/\s*\(\d+\)\s*$/, '');
        var newPeriod = newSettings.period || info.period;
        var newMult = newSettings.multiplier || info.multiplier || 2;

        if (type === 'moving-average-ex') {
            var maSource = newSettings.source || info.source || 'close';
            var maMethod = newSettings.method || info.method || 'SMA';
            var maLen = Math.max(1, newPeriod);
            var maVals;
            if (maMethod === 'HMA') {
                maVals = _computeHMA(rawData, maLen, maSource);
            } else if (maMethod === 'VWMA') {
                maVals = _computeVWMA(rawData, maLen, maSource);
            } else {
                var maBase = rawData.map(function(p) { return { time: p.time, value: _tvIndicatorValue(p, maSource) }; });
                var maFn = maMethod === 'EMA' ? _computeEMA : (maMethod === 'WMA' ? _computeWMA : _computeSMA);
                maVals = maFn(maBase, maLen, 'value');
            }
            var maSeries = entry.seriesMap[seriesId];
            if (maSeries) maSeries.setData(maVals.filter(function(v) { return v.value !== undefined; }));
            info.period = maLen;
            info.source = maSource;
            info.method = maMethod;
        } else if (type === 'momentum') {
            var momSource = newSettings.source || info.source || 'close';
            var momSeries = entry.seriesMap[seriesId];
            if (momSeries) momSeries.setData(_tvComputeMomentum(rawData, Math.max(1, newPeriod), momSource).filter(function(v) { return v.value !== undefined; }));
            info.period = Math.max(1, newPeriod);
            info.source = momSource;
        } else if (type === 'percent-change') {
            var pcSource = newSettings.source || info.source || 'close';
            var pcSeries = entry.seriesMap[seriesId];
            if (pcSeries) pcSeries.setData(_tvComputePercentChange(rawData, pcSource).filter(function(v) { return v.value !== undefined; }));
            info.source = pcSource;
        } else if (type === 'correlation') {
            var secData = _tvSeriesRawData(entry, info.secondarySeriesId);
            var cSeries = entry.seriesMap[seriesId];
            var psrc = newSettings.primarySource || info.primarySource || 'close';
            var ssrc = newSettings.secondarySource || info.secondarySource || 'close';
            if (cSeries) cSeries.setData(_tvComputeCorrelation(rawData, secData, Math.max(2, newPeriod), psrc, ssrc).filter(function(v) { return v.value !== undefined; }));
            info.period = Math.max(2, newPeriod);
            info.primarySource = psrc;
            info.secondarySource = ssrc;
        } else if (type === 'spread' || type === 'ratio' || type === 'sum' || type === 'product') {
            var secData2 = _tvSeriesRawData(entry, info.secondarySeriesId);
            var biSeries = entry.seriesMap[seriesId];
            var psrc2 = newSettings.primarySource || info.primarySource || 'close';
            var ssrc2 = newSettings.secondarySource || info.secondarySource || 'close';
            if (biSeries) biSeries.setData(_tvComputeBinary(rawData, secData2, psrc2, ssrc2, type).filter(function(v) { return v.value !== undefined; }));
            info.primarySource = psrc2;
            info.secondarySource = ssrc2;
        } else if (type === 'average-price') {
            var apSeries = entry.seriesMap[seriesId];
            if (apSeries) apSeries.setData(_tvComputeAveragePrice(rawData).filter(function(v) { return v.value !== undefined; }));
        } else if (type === 'median-price') {
            var mpSeries = entry.seriesMap[seriesId];
            if (mpSeries) mpSeries.setData(_tvComputeMedianPrice(rawData).filter(function(v) { return v.value !== undefined; }));
        } else if (type === 'weighted-close') {
            var wcSeries = entry.seriesMap[seriesId];
            if (wcSeries) wcSeries.setData(_tvComputeWeightedClose(rawData).filter(function(v) { return v.value !== undefined; }));
        } else if (info.group && type === 'bollinger-bands') {
            var bbSource = newSettings.source || info.source || 'close';
            var bbMaType = newSettings.maType || info.maType || 'SMA';
            var bbOffset = newSettings.offset !== undefined ? newSettings.offset : (info.offset || 0);
            var bbBase = rawData.map(function(p) { return { time: p.time, close: _tvIndicatorValue(p, bbSource) }; });
            var bb2 = _computeBollingerBands(bbBase, newPeriod, newMult, bbMaType, bbOffset);
            var gKeys = Object.keys(_activeIndicators);
            for (var gi = 0; gi < gKeys.length; gi++) {
                if (_activeIndicators[gKeys[gi]].group !== info.group) continue;
                _activeIndicators[gKeys[gi]].period = newPeriod;
                _activeIndicators[gKeys[gi]].multiplier = newMult;
                _activeIndicators[gKeys[gi]].source = bbSource;
                _activeIndicators[gKeys[gi]].maType = bbMaType;
                _activeIndicators[gKeys[gi]].offset = bbOffset;
                var gs2 = entry.seriesMap[gKeys[gi]];
                var bbD = gKeys[gi].indexOf('upper') >= 0 ? bb2.upper : gKeys[gi].indexOf('lower') >= 0 ? bb2.lower : bb2.middle;
                if (gs2) gs2.setData(bbD.filter(function(v) { return v.value !== undefined; }));
            }
        } else if (info.name === 'RSI') {
            var rsiSource = newSettings.source || info.source || 'close';
            var rsiBase = rawData.map(function(p) { return { time: p.time, close: _tvIndicatorValue(p, rsiSource) }; });
            var rsN = entry.seriesMap[seriesId];
            if (rsN) rsN.setData(_computeRSI(rsiBase, newPeriod).filter(function(v) { return v.value !== undefined; }));
            info.period = newPeriod;
            info.source = rsiSource;
        } else if (info.name === 'ATR') {
            var atN = entry.seriesMap[seriesId];
            if (atN) atN.setData(_computeATR(rawData, newPeriod).filter(function(v) { return v.value !== undefined; }));
            info.period = newPeriod;
        } else if (info.name === 'Volume SMA') {
            var vN = entry.seriesMap[seriesId];
            if (vN) vN.setData(_computeSMA(rawData, newPeriod, 'volume').filter(function(v) { return v.value !== undefined; }));
            info.period = newPeriod;

        // ----- New indicators: single-series -----
        } else if (info.name === 'CCI') {
            var cciSrc2 = newSettings.source || info.source || 'hlc3';
            var cciSer = entry.seriesMap[seriesId];
            if (cciSer) cciSer.setData(_computeCCI(rawData, newPeriod, cciSrc2).filter(function(v) { return v.value !== undefined; }));
            info.period = newPeriod;
            info.source = cciSrc2;
        } else if (info.name === 'Williams %R') {
            var wrSrc2 = newSettings.source || info.source || 'close';
            var wrSer = entry.seriesMap[seriesId];
            if (wrSer) wrSer.setData(_computeWilliamsR(rawData, newPeriod, wrSrc2).filter(function(v) { return v.value !== undefined; }));
            info.period = newPeriod;
            info.source = wrSrc2;
        } else if (info.name === 'Accumulation/Distribution') {
            var adSer = entry.seriesMap[seriesId];
            if (adSer) adSer.setData(_computeAccumulationDistribution(rawData).filter(function(v) { return v.value !== undefined; }));
        } else if (info.name === 'Historical Volatility') {
            var hvAnn = newSettings.annualization || info.annualization || 252;
            var hvSer = entry.seriesMap[seriesId];
            if (hvSer) hvSer.setData(_computeHistoricalVolatility(rawData, newPeriod, hvAnn).filter(function(v) { return v.value !== undefined; }));
            info.period = newPeriod;
            info.annualization = hvAnn;
        } else if (info.type === 'parabolic-sar') {
            var psStep = newSettings.step || info.step || 0.02;
            var psMax = newSettings.maxStep || info.maxStep || 0.2;
            var psSer = entry.seriesMap[seriesId];
            if (psSer) psSer.setData(_computeParabolicSAR(rawData, psStep, psMax).filter(function(v) { return v.value !== undefined; }));
            info.step = psStep;
            info.maxStep = psMax;

        // ----- New indicators: grouped (multi-series) -----
        } else if (info.group && info.type === 'macd') {
            var macdFast = newSettings.fast || info.fast || 12;
            var macdSlow = newSettings.slow || info.slow || 26;
            var macdSig = newSettings.signal || info.signal || 9;
            var macdSrc = newSettings.macdSource || info.macdSource || 'close';
            var macdOsc = newSettings.oscMaType || info.oscMaType || 'EMA';
            var macdSigType = newSettings.signalMaType || info.signalMaType || 'EMA';
            var macdRes = _computeMACD(rawData, macdFast, macdSlow, macdSig, macdSrc, macdOsc, macdSigType);
            var macdHistData = macdRes.histogram.filter(function(v) { return v.value !== undefined; }).map(function(v) {
                return { time: v.time, value: v.value, color: v.value >= 0 ? (info.histPosColor || _cssVar('--pywry-tvchart-ind-positive-dim')) : (info.histNegColor || _cssVar('--pywry-tvchart-ind-negative-dim')) };
            });
            var mKeys = Object.keys(_activeIndicators);
            for (var mi = 0; mi < mKeys.length; mi++) {
                if (_activeIndicators[mKeys[mi]].group !== info.group) continue;
                _activeIndicators[mKeys[mi]].fast = macdFast;
                _activeIndicators[mKeys[mi]].slow = macdSlow;
                _activeIndicators[mKeys[mi]].signal = macdSig;
                _activeIndicators[mKeys[mi]].macdSource = macdSrc;
                _activeIndicators[mKeys[mi]].oscMaType = macdOsc;
                _activeIndicators[mKeys[mi]].signalMaType = macdSigType;
                _activeIndicators[mKeys[mi]].period = macdFast;
                var mSer = entry.seriesMap[mKeys[mi]];
                if (!mSer) continue;
                if (mKeys[mi].indexOf('hist') >= 0) mSer.setData(macdHistData);
                else if (mKeys[mi].indexOf('signal') >= 0) mSer.setData(macdRes.signal.filter(function(v) { return v.value !== undefined; }));
                else mSer.setData(macdRes.macd.filter(function(v) { return v.value !== undefined; }));
            }
        } else if (info.group && info.type === 'stochastic') {
            var stochK = newSettings.kPeriod || newSettings.period || info.kPeriod || newPeriod;
            var stochKS = newSettings.kSmoothing || info.kSmoothing || 1;
            var stochD = newSettings.dPeriod || info.dPeriod || 3;
            var stochRes = _computeStochastic(rawData, stochK, stochKS, stochD);
            var sKeysAll = Object.keys(_activeIndicators);
            for (var si = 0; si < sKeysAll.length; si++) {
                if (_activeIndicators[sKeysAll[si]].group !== info.group) continue;
                _activeIndicators[sKeysAll[si]].kPeriod = stochK;
                _activeIndicators[sKeysAll[si]].kSmoothing = stochKS;
                _activeIndicators[sKeysAll[si]].dPeriod = stochD;
                _activeIndicators[sKeysAll[si]].period = stochK;
                var stSer = entry.seriesMap[sKeysAll[si]];
                if (!stSer) continue;
                if (sKeysAll[si].indexOf('_d_') >= 0) stSer.setData(stochRes.d.filter(function(v) { return v.value !== undefined; }));
                else stSer.setData(stochRes.k.filter(function(v) { return v.value !== undefined; }));
            }
        } else if (info.group && info.type === 'aroon') {
            var arRes = _computeAroon(rawData, newPeriod);
            var aKeys = Object.keys(_activeIndicators);
            for (var ai2 = 0; ai2 < aKeys.length; ai2++) {
                if (_activeIndicators[aKeys[ai2]].group !== info.group) continue;
                _activeIndicators[aKeys[ai2]].period = newPeriod;
                var arSer = entry.seriesMap[aKeys[ai2]];
                if (!arSer) continue;
                if (aKeys[ai2].indexOf('down') >= 0) arSer.setData(arRes.down.filter(function(v) { return v.value !== undefined; }));
                else arSer.setData(arRes.up.filter(function(v) { return v.value !== undefined; }));
            }
        } else if (info.group && info.type === 'adx') {
            var adxDi2 = newSettings.diLength || info.diLength || newPeriod;
            var adxSm2 = newSettings.adxSmoothing || info.adxSmoothing || newPeriod;
            var adxRes = _computeADX(rawData, adxDi2, adxSm2);
            var adKeys = Object.keys(_activeIndicators);
            for (var di = 0; di < adKeys.length; di++) {
                if (_activeIndicators[adKeys[di]].group !== info.group) continue;
                _activeIndicators[adKeys[di]].period = adxSm2;
                _activeIndicators[adKeys[di]].adxSmoothing = adxSm2;
                _activeIndicators[adKeys[di]].diLength = adxDi2;
                var adSer2 = entry.seriesMap[adKeys[di]];
                if (!adSer2) continue;
                if (adKeys[di].indexOf('plus') >= 0) adSer2.setData(adxRes.plusDI.filter(function(v) { return v.value !== undefined; }));
                else if (adKeys[di].indexOf('minus') >= 0) adSer2.setData(adxRes.minusDI.filter(function(v) { return v.value !== undefined; }));
                else adSer2.setData(adxRes.adx.filter(function(v) { return v.value !== undefined; }));
            }
        } else if (info.group && info.type === 'keltner-channels') {
            var kcMult = newSettings.multiplier || info.multiplier || 2;
            var kcMaType = newSettings.maType || info.maType || 'EMA';
            var kcRes = _computeKeltnerChannels(rawData, newPeriod, kcMult, kcMaType);
            var kKeys = Object.keys(_activeIndicators);
            for (var ki = 0; ki < kKeys.length; ki++) {
                if (_activeIndicators[kKeys[ki]].group !== info.group) continue;
                _activeIndicators[kKeys[ki]].period = newPeriod;
                _activeIndicators[kKeys[ki]].multiplier = kcMult;
                _activeIndicators[kKeys[ki]].maType = kcMaType;
                var kSer = entry.seriesMap[kKeys[ki]];
                if (!kSer) continue;
                if (kKeys[ki].indexOf('upper') >= 0) kSer.setData(kcRes.upper.filter(function(v) { return v.value !== undefined; }));
                else if (kKeys[ki].indexOf('lower') >= 0) kSer.setData(kcRes.lower.filter(function(v) { return v.value !== undefined; }));
                else kSer.setData(kcRes.middle.filter(function(v) { return v.value !== undefined; }));
            }
        } else if (info.group && info.type === 'ichimoku') {
            var ichConv = newSettings.conversionPeriod || newSettings.tenkan || info.conversionPeriod || info.tenkan || 9;
            var ichBase = newSettings.basePeriod || newSettings.kijun || info.basePeriod || info.kijun || newPeriod || 26;
            var ichLead = newSettings.leadingSpanPeriod || newSettings.senkouB || info.leadingSpanPeriod || info.senkouB || 52;
            var ichLag = newSettings.laggingPeriod || info.laggingPeriod || 26;
            var ichShift = newSettings.leadingShiftPeriod || info.leadingShiftPeriod || 26;
            var ichRes = _computeIchimoku(rawData, ichConv, ichBase, ichLead, ichLag, ichShift);
            var iKeys = Object.keys(_activeIndicators);
            for (var ii = 0; ii < iKeys.length; ii++) {
                if (_activeIndicators[iKeys[ii]].group !== info.group) continue;
                var ai = _activeIndicators[iKeys[ii]];
                ai.conversionPeriod = ichConv;
                ai.basePeriod = ichBase;
                ai.leadingSpanPeriod = ichLead;
                ai.laggingPeriod = ichLag;
                ai.leadingShiftPeriod = ichShift;
                ai.tenkan = ichConv; ai.kijun = ichBase; ai.senkouB = ichLead;
                ai.period = ichBase;
                var iSer = entry.seriesMap[iKeys[ii]];
                if (!iSer) continue;
                var k = iKeys[ii];
                if (k.indexOf('tenkan') >= 0) iSer.setData(ichRes.tenkan.filter(function(v) { return v.value !== undefined; }));
                else if (k.indexOf('kijun') >= 0) iSer.setData(ichRes.kijun.filter(function(v) { return v.value !== undefined; }));
                else if (k.indexOf('spanA') >= 0) iSer.setData(ichRes.spanA.filter(function(v) { return v.value !== undefined; }));
                else if (k.indexOf('spanB') >= 0) iSer.setData(ichRes.spanB.filter(function(v) { return v.value !== undefined; }));
                else if (k.indexOf('chikou') >= 0) iSer.setData(ichRes.chikou.filter(function(v) { return v.value !== undefined; }));
            }
        }
    }
    // Volume Profile: apply settings + recompute if anything that
    // affects the bucket layout changed (rows-layout / row-size /
    // developing-poc/va toggles).
    if (type === 'volume-profile-fixed' || type === 'volume-profile-visible') {
        var vpSlot = _volumeProfilePrimitives[seriesId];
        if (vpSlot) {
            var prevOpts = vpSlot.opts || {};
            var newRowsLayout = newSettings.vpRowsLayout || vpSlot.rowsLayout || 'rows';
            var newRowSize = newSettings.vpRowSize != null ? Number(newSettings.vpRowSize) : vpSlot.rowSize;
            var newVolumeMode = newSettings.vpVolumeMode || vpSlot.volumeMode || 'updown';
            var newValueAreaPct = newSettings.vpValueAreaPct != null
                ? newSettings.vpValueAreaPct / 100
                : (prevOpts.valueAreaPct || 0.70);
            var newShowDevPOC = newSettings.vpShowDevelopingPOC === true;
            var newShowDevVA = newSettings.vpShowDevelopingVA === true;

            vpSlot.opts = {
                rowsLayout: newRowsLayout,
                rowSize: newRowSize,
                volumeMode: newVolumeMode,
                widthPercent: newSettings.vpWidthPercent != null ? newSettings.vpWidthPercent : prevOpts.widthPercent,
                placement: newSettings.vpPlacement || prevOpts.placement || 'right',
                upColor: newSettings.vpUpColor || prevOpts.upColor,
                downColor: newSettings.vpDownColor || prevOpts.downColor,
                vaUpColor: newSettings.vpVAUpColor || prevOpts.vaUpColor,
                vaDownColor: newSettings.vpVADownColor || prevOpts.vaDownColor,
                pocColor: newSettings.vpPOCColor || prevOpts.pocColor,
                developingPOCColor: newSettings.vpDevelopingPOCColor || prevOpts.developingPOCColor,
                developingVAColor: newSettings.vpDevelopingVAColor || prevOpts.developingVAColor,
                showPOC: newSettings.vpShowPOC !== undefined ? newSettings.vpShowPOC : prevOpts.showPOC,
                showValueArea: newSettings.vpShowValueArea !== undefined ? newSettings.vpShowValueArea : prevOpts.showValueArea,
                showDevelopingPOC: newShowDevPOC,
                showDevelopingVA: newShowDevVA,
                valueAreaPct: newValueAreaPct,
            };

            // Recompute when any compute-affecting field changed
            var needsRecompute = newRowsLayout !== vpSlot.rowsLayout
                || newRowSize !== vpSlot.rowSize
                || newValueAreaPct !== (prevOpts.valueAreaPct || 0.70)
                || newShowDevPOC !== (prevOpts.showDevelopingPOC === true)
                || newShowDevVA !== (prevOpts.showDevelopingVA === true);
            if (needsRecompute) {
                vpSlot.rowsLayout = newRowsLayout;
                vpSlot.rowSize = newRowSize;
                vpSlot.volumeMode = newVolumeMode;
                var fromIdx = info.fromIndex != null ? info.fromIndex : 0;
                var toIdx = info.toIndex != null ? info.toIndex : (rawData.length - 1);
                var newVp = _tvComputeVolumeProfile(rawData, fromIdx, toIdx, {
                    rowsLayout: newRowsLayout,
                    rowSize: newRowSize,
                    valueAreaPct: newValueAreaPct,
                    withDeveloping: newShowDevPOC || newShowDevVA,
                });
                if (newVp) vpSlot.vpData = newVp;
            } else {
                vpSlot.volumeMode = newVolumeMode;
            }

            info.rowsLayout = newRowsLayout;
            info.rowSize = newRowSize;
            info.volumeMode = newVolumeMode;
            info.period = newRowsLayout === 'rows' ? newRowSize : 0;
            info.widthPercent = vpSlot.opts.widthPercent;
            info.placement = vpSlot.opts.placement;
            info.upColor = vpSlot.opts.upColor;
            info.downColor = vpSlot.opts.downColor;
            info.vaUpColor = vpSlot.opts.vaUpColor;
            info.vaDownColor = vpSlot.opts.vaDownColor;
            info.pocColor = vpSlot.opts.pocColor;
            info.developingPOCColor = vpSlot.opts.developingPOCColor;
            info.developingVAColor = vpSlot.opts.developingVAColor;
            info.showPOC = vpSlot.opts.showPOC;
            info.showValueArea = vpSlot.opts.showValueArea;
            info.showDevelopingPOC = newShowDevPOC;
            info.showDevelopingVA = newShowDevVA;
            info.valueAreaPct = newValueAreaPct;
            if (newSettings.vpLabelsOnPriceScale !== undefined) info.labelsOnPriceScale = newSettings.vpLabelsOnPriceScale;
            if (newSettings.vpValuesInStatusLine !== undefined) info.valuesInStatusLine = newSettings.vpValuesInStatusLine;
            if (newSettings.vpInputsInStatusLine !== undefined) info.inputsInStatusLine = newSettings.vpInputsInStatusLine;

            if (vpSlot.primitive && vpSlot.primitive.triggerUpdate) vpSlot.primitive.triggerUpdate();
        }
    }

    _tvRebuildIndicatorLegend(info.chartId);
    // Re-render BB fills after settings change
    if (type === 'bollinger-bands') {
        _tvEnsureBBFillPrimitive(info.chartId);
        _tvUpdateBBFill(info.chartId);
    }
    // Re-render Ichimoku Kumo after settings change
    if (type === 'ichimoku') {
        _tvEnsureIchimokuCloudPrimitive(info.chartId);
        _tvUpdateIchimokuCloud(info.chartId);
    }
}

