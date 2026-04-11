# pywry.tvchart.models

Data models for the TradingView datafeed request/response protocol.
These Pydantic models define symbol metadata, bar data, and the
wire format for chart ↔ Python communication.

---

## Symbol Metadata

::: pywry.tvchart.models.TVChartSymbolInfo
    options:
      show_root_heading: true
      heading_level: 3
      members: true

---

## Bar Data

::: pywry.tvchart.models.TVChartSeriesData
    options:
      show_root_heading: true
      heading_level: 3
      members: true

::: pywry.tvchart.models.TVChartData
    options:
      show_root_heading: true
      heading_level: 3
      members: true

---

## Datafeed Requests (JS → Python)

::: pywry.tvchart.models.TVChartDatafeedConfigRequest
    options:
      show_root_heading: true
      heading_level: 3

::: pywry.tvchart.models.TVChartDatafeedSearchRequest
    options:
      show_root_heading: true
      heading_level: 3

::: pywry.tvchart.models.TVChartDatafeedResolveRequest
    options:
      show_root_heading: true
      heading_level: 3

::: pywry.tvchart.models.TVChartDatafeedHistoryRequest
    options:
      show_root_heading: true
      heading_level: 3

::: pywry.tvchart.models.TVChartDatafeedSubscribeRequest
    options:
      show_root_heading: true
      heading_level: 3

::: pywry.tvchart.models.TVChartDatafeedUnsubscribeRequest
    options:
      show_root_heading: true
      heading_level: 3

::: pywry.tvchart.models.TVChartDatafeedMarksRequest
    options:
      show_root_heading: true
      heading_level: 3

::: pywry.tvchart.models.TVChartDatafeedTimescaleMarksRequest
    options:
      show_root_heading: true
      heading_level: 3

::: pywry.tvchart.models.TVChartDatafeedServerTimeRequest
    options:
      show_root_heading: true
      heading_level: 3
