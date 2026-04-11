# pywry.tvchart (Mixin & Helpers)

The `TVChartStateMixin` is the main Python ↔ JS bridge for TradingView charts.
It provides methods for updating data, managing series, controlling the UI,
and implementing the full datafeed protocol.

---

## TVChartStateMixin

::: pywry.tvchart.mixin.TVChartStateMixin
    options:
      show_root_heading: true
      heading_level: 2
      members: true
      members_order: source
      inherited_members: false

---

## Data Normalization

::: pywry.tvchart.normalize.normalize_ohlcv
    options:
      show_root_heading: true
      heading_level: 3

---

## Toolbar Builder

::: pywry.tvchart.toolbars.build_tvchart_toolbars
    options:
      show_root_heading: true
      heading_level: 3
