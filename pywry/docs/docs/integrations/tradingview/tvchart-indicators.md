# TradingView Indicators

Catalog of every indicator available in the TradingView Lightweight Charts
integration.  Each entry is exposed in the Indicators panel UI, addable via
`tvchart:add-indicator` / `app.add_builtin_indicator(name, ...)`, and
recomputed automatically when underlying bars change (scrollback, interval
switch, symbol change, session-filter toggle).

Every indicator's settings dialog mirrors TradingView's real field labels.
Field-level parameters passed via `app.add_builtin_indicator()` prefix
non-`period`/`color`/`source` arguments with an underscore so the frontend
can route them to the right indicator-specific slot.

!!! note "Where colors come from"
    Indicator colors are never hard-coded.  Multi-series indicators read
    from the `--pywry-tvchart-ind-*` CSS palette (primary, secondary, etc.)
    so they stay theme-aware — see
    [CSS Reference → Indicator Palette](../../reference/css/tvchart.md#indicator-palette).

## Moving Averages

### Moving Average (unified SMA / EMA / WMA / HMA / VWMA)

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `period` (Length) | int | 9 | Lookback window |
| `method` | `SMA` \| `EMA` \| `WMA` \| `HMA` \| `VWMA` | `SMA` | Selected from the Type dropdown |
| `source` | `close` \| `open` \| `high` \| `low` \| `hl2` \| `hlc3` \| `ohlc4` | `close` | Input series |
| `color` | CSS color | palette primary | Line color |

A single catalog entry, not five separate ones — picking a different Type
in the settings dialog triggers the appropriate compute function (`_computeSMA`,
`_computeEMA`, `_computeWMA`, `_computeHMA`, `_computeVWMA`).

### Ichimoku Cloud (`Ichimoku Cloud`)

Five-line indicator using TradingView's exact parameter names:

| Parameter | Default | Line |
|-----------|---------|------|
| Conversion Line Periods | 9 | Tenkan-sen |
| Base Line Periods | 26 | Kijun-sen |
| Leading Span Periods | 52 | Senkou Span B |
| Lagging Span Periods | 26 | Chikou Span (back-shifted close) |
| Leading Shift Periods | 26 | Forward shift applied to Senkou A/B |

Senkou A/B are rendered with a translucent cloud fill via the
`_tvMakeIchimokuCloudPrimitive` primitive so the crossover region actually
projects into the future, matching TradingView's reference.

## Volatility

### Bollinger Bands (`Bollinger Bands`)

| Parameter | Default | |
|-----------|---------|-|
| `period` | 20 | SMA window |
| `multiplier` | 2 | StdDev multiplier |
| `maType` | `SMA` | Can be `SMA` / `EMA` / `WMA` |
| `source` | `close` | |
| `offset` | 0 | Forward / back shift in bars |

Renders three line series (upper / middle / lower) plus the `bb-fill` primitive.

### Keltner Channels (`Keltner Channels`)

| Parameter | Default | |
|-----------|---------|-|
| `period` (Length) | 20 | Middle-line window |
| `multiplier` | 2 | ATR multiplier applied above/below the middle |
| `maType` | `EMA` | Middle-line MA type |

### Average True Range (`ATR`)

Single-series subplot.  Parameter: `period` (default 14).

### Historical Volatility (`Historical Volatility`)

Standard deviation of log returns, annualized.

| Parameter | Default |
|-----------|---------|
| `period` | 10 |
| `_annualization` | 252 (trading days per year) |

### Parabolic SAR (`Parabolic SAR`)

Trend-following dot series rendered on the main pane.

| Parameter | Default |
|-----------|---------|
| `_step` (acceleration factor start) | 0.02 |
| `_maxStep` (maximum AF) | 0.2 |

## Momentum

### Relative Strength Index (`RSI`)

Subplot oscillator.  Parameter: `period` (default 14), `source` (default `close`).

### MACD (`MACD`)

Subplot with three series (MACD line, Signal line, Histogram).

| Parameter | Default |
|-----------|---------|
| `_fast` | 12 |
| `_slow` | 26 |
| `_signal` | 9 |
| `_oscMaType` | `EMA` |
| `_signalMaType` | `EMA` |
| `source` | `close` |

Histogram bars are colored per-bar from `--pywry-tvchart-ind-positive-dim`
/ `--pywry-tvchart-ind-negative-dim`; the recompute path reapplies those
colors every time the bars refresh (otherwise scrollback would strip them).

### Stochastic (`Stochastic`)

| Parameter | Default | TradingView label |
|-----------|---------|-------------------|
| `period` | 14 | %K Period |
| `_kSmoothing` | 1 | %K Smoothing |
| `_dPeriod` | 3 | %D Period |

### Williams %R (`Williams %R`)

Oscillator between 0 and -100.  Parameter: `period` (default 14), `source`.

### CCI (`CCI`)

Commodity Channel Index.  Parameter: `period` (default 20), `source` (default `hlc3`).

### ADX (`ADX`)

Three-series subplot (`ADX`, `+DI`, `-DI`).

| Parameter | Default |
|-----------|---------|
| `_diLength` | 14 |
| `_adxSmoothing` | 14 |

### Aroon (`Aroon`)

Two-series subplot (`Aroon Up`, `Aroon Down`).  Parameter: `period` (default 14).

## Volume

### VWAP (`VWAP`)

Cumulative volume-weighted average price.  Rendered on the main pane.  No
user parameters — session anchoring follows the current bar series.

### Volume SMA (`Volume SMA`)

Moving average of the volume histogram.  Parameter: `period` (default 20).

### Accumulation / Distribution Line (`Accumulation/Distribution`)

Cumulative money-flow line.  Rendered in its own subplot pane (not inside
the volume pane).  Values can grow into the trillions, so the right-axis
formatter shortens them to K / M / B / T.

### Volume Profile Fixed Range (`Volume Profile Fixed Range`)

Right-pinned horizontal histogram of volume traded at each price bucket
across a fixed bar-index range.  Splits each row into up-volume and
down-volume, marks the Point of Control (POC), and shades the 70 % Value
Area.

| Parameter | Default | Notes |
|-----------|---------|-------|
| `_rowSize` | 24 | Bucket count in `rows` layout, or price increment in `ticks` layout |
| `_rowsLayout` | `rows` | `rows` (count) or `ticks` (price-increment) |
| `_valueAreaPct` | 0.70 | Fraction of total volume to enclose in VA band |
| `_showDevelopingPOC` | false | Draw the running POC as a step-line across time |
| `_showDevelopingVA` | false | Draw the running VA high/low across time |

Color surfaces come exclusively from the `--pywry-tvchart-vp-*` CSS variables.

### Volume Profile Visible Range (`Volume Profile Visible Range`)

Same shape as the fixed-range version but the bucket range tracks the
timescale's visible logical range.  As the user pans / zooms, the profile
recomputes on every frame via `_tvRefreshVisibleVolumeProfiles()`.

## Lightweight Examples (single-series utilities)

Derived plots included mainly as examples of the compute-to-line pipeline:

| Name | Parameters | Subplot? |
|------|-----------|----------|
| Average Price | — | No |
| Median Price | — | No |
| Weighted Close | — | No |
| Momentum | `period` (10) | Yes |
| Percent Change | `source` | Yes |
| Correlation | `period` (20), `primarySource`, `secondarySource`, second symbol | Yes |
| Product / Ratio / Spread / Sum | `primarySource`, `secondarySource`, second symbol | Yes |

## Recompute contract

Every indicator above lists at least one `_compute*` function in the
frontend JS bundle **and** a matching branch in
`_tvRecomputeIndicatorSeries`.  The recompute branch fires on:

- Datafeed scrollback — older bars prepended to `_seriesRawData`.
- Interval change — bars replaced in a destroy / recreate cycle.
- Symbol change — main series swapped.
- Session filter toggle (RTH / ETH) — the displayed bar set changes.

Without the recompute branch, an indicator silently freezes at its initial
snapshot while the candles below it update — the bug that produced
`VWAP = 9.99` on a $270 stock (initial bars were placeholder values; the
datafeed replaced them but VWAP never refreshed).

## Tests

`pywry/tests/test_tvchart.py` enforces the contract:

- `TestTVChartIndicatorCatalog.test_catalog_contains_indicator` — every
  expected name is in the catalog.
- `TestTVChartIndicatorCatalog.test_compute_function_defined` — every
  `_compute*` function exists.
- `TestTVChartIndicatorCatalog.test_add_branch_wires_compute` — the add
  branch calls the compute function.
- `TestTVChartIndicatorCatalog.test_recompute_branch_refreshes_series` —
  the recompute branch exists and calls the compute function.
- `TestTVChartIndicatorCatalog.test_recompute_branch_for_volume_profile` —
  visible-range VP is refreshed via `_tvRefreshVisibleVolumeProfiles`.
- `TestTVChartVolumeProfile` — VP profile returns
  `profile / minPrice / maxPrice / step / totalVolume`, splits up vs down
  volume per row, and exposes a POC / Value Area helper.
- `TestTVChartThemeVariables` — every `--pywry-tvchart-vp-*` and
  `--pywry-tvchart-ind-*` CSS variable is defined in both the dark and
  light theme blocks.
- `TestTVChartLegendVolumeRemoval` — clicking "Remove" on the volume
  legend row actually calls `chart.removeSeries`, removes the empty pane,
  and reindexes the remaining panes (previously it only toggled a
  dataset flag).
