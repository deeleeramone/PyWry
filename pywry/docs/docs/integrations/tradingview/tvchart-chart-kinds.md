# Chart kinds (`chart_kind`)

Lightweight Charts 5 ships three chart factories. PyWry routes between
them via a single `chart_kind` parameter on `PyWry.show_tvchart(...)`
(and the underlying [`TVChartConfig.chart_kind`][pywry.tvchart.config.TVChartConfig]
model).

| `chart_kind`    | LWC factory             | X axis           | Typical use |
|-----------------|-------------------------|------------------|-------------|
| `"default"`     | `createChart`           | Time             | OHLC candles, tick series, any time-indexed data |
| `"price"`       | `createOptionsChart`    | Numeric price    | Option payoff diagrams, IV smile/skew, volume-by-strike, order-book depth, probability distributions |
| `"yield-curve"` | `createYieldCurveChart` | Tenor in months  | Treasury / SOFR / OIS / swap / credit curves, futures term structure, forward curves |

The factories share the same palette, layout, interaction, and scale
defaults — only the horizontal-scale semantics differ. Time-axis-only
subsystems (interval tabs, session filter, volume auto-extract,
scrollback) are gated off when `chart_kind != "default"`.

## `"default"` — time-axis chart

The standard equities / crypto / futures chart. No additional
configuration needed.

```python
from pywry import PyWry

app = PyWry()
app.show_tvchart(
    data=[
        {"time": 1700000000, "open": 100, "high": 103, "low": 99, "close": 102, "volume": 1_200_000},
        ...
    ],
    title="SPY",
)
app.block()
```

## `"price"` — numeric-price X axis (`createOptionsChart`)

Data points use a numeric `time` field that represents the price level,
not a timestamp. Use this factory for anything indexed by price or
strike rather than by time.

```python
app.show_tvchart(
    data=[
        {"time": 225.0, "value": -5.20},   # payoff at spot 225
        {"time": 275.0, "value": -5.20},   # payoff at spot 275 (at strike)
        {"time": 325.0, "value":  44.80},  # payoff at spot 325
    ],
    title="Long Call — Strike $275",
    chart_kind="price",
    series_options={"seriesType": "Line", "color": "#26a69a"},
)
```

Suitable for:

- Option-chain payoff diagrams (profit / loss vs. underlying at expiry)
- Implied-volatility smile / skew (IV vs. strike)
- Volume-by-strike bars (open interest or traded volume per strike)
- Market-profile / volume-profile views rendered as their own chart
- Probability distributions and PDF / CDF overlays
- Order-book depth (size vs. price)

## `"yield-curve"` — tenor-in-months X axis (`createYieldCurveChart`)

Data points use a numeric `time` field measured in months of tenor. The
factory spaces tenors linearly so 3M and 6M sit adjacent and 2Y / 10Y
are eight linear units apart — unlike a time-axis chart which would
render them years apart.

```python
app.show_tvchart(
    data=[
        {"time": 1,   "value": 4.38},  # 1M
        {"time": 3,   "value": 4.30},
        {"time": 12,  "value": 3.95},  # 1Y
        {"time": 24,  "value": 3.80},  # 2Y
        {"time": 120, "value": 4.35},  # 10Y
        {"time": 360, "value": 4.58},  # 30Y
    ],
    title="US Treasury Yield Curve",
    chart_kind="yield-curve",
    yield_curve={
        "baseResolution":    1,    # one month per step
        "minimumTimeRange":  360,  # visible span: 30y
        "startTimeRange":    0,    # axis starts at tenor 0
    },
    series_options={"seriesType": "Line", "color": "#4c87ff"},
)
```

Suitable for:

- US Treasury / sovereign yield curves
- SOFR / OIS / LIBOR swap curves
- Credit-spread curves
- Forward-rate curves
- Futures term structure (contango / backwardation visualisations —
  VX futures, oil contracts, etc.)
- Any generic "value vs. tenor" chart

## `yield_curve` options

Forwarded to the yield-curve factory. Ignored unless `chart_kind == "yield-curve"`.

| Field               | Default | Meaning |
|---------------------|---------|---------|
| `baseResolution`    | `1`     | Smallest time unit (typically 1 month). |
| `minimumTimeRange`  | `120`   | Minimum visible range in `baseResolution` units. |
| `startTimeRange`    | `0`     | Where the axis starts, in `baseResolution` units. |
| `formatTime`        | —       | Optional custom tenor-label formatter (injected as JS — pass via `chart_options.localization.timeFormatter` instead when going through the Python API). |

## Runnable example

`examples/pywry_demo_tvchart.ipynb` contains cells that render both
factories — open the notebook and run the "Yield Curve Chart" and
"Options Payoff Chart" sections after the default chart demo.
