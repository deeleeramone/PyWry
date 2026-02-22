"""PyWry Multi-Widget Demo — Plotly + AG Grid + Toolbar in one window.

Demonstrates combining a Plotly chart, AG Grid table, KPI cards, and a
detail panel in a single ``app.show()`` call.  Every piece uses the
library's built-in integrations — ``build_plotly_init_script``,
``build_grid_html``, toolbars, and the bidirectional event system.

Cross-widget interactions (no inline JS required):
  • Select grid rows  →  chart redraws showing only selected products
  • Click a chart bar  →  detail panel shows that product's breakdown
  • Toolbar chart-type selector  →  live chart type switch
  • Export button  →  CSV download via ``pywry:download``

Works from all rendering paths (native window, notebook, iframe, browser).
"""

import json

import pandas as pd
import plotly.graph_objects as go

from pywry import (
    Button,
    HtmlContent,
    Option,
    PyWry,
    Select,
    ThemeMode,
    Toolbar,
)
from pywry.grid import build_grid_config, build_grid_html
from pywry.templates import build_plotly_init_script


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SALES = pd.DataFrame(
    {
        "Product": ["Widget A", "Widget B", "Widget C", "Widget D", "Widget E"],
        "Q1": [12_000, 18_000, 7_500, 22_000, 9_500],
        "Q2": [14_500, 16_000, 11_000, 19_000, 13_000],
        "Q3": [16_000, 21_000, 9_000, 25_000, 11_500],
        "Q4": [19_000, 17_500, 13_500, 28_000, 15_000],
    }
)

QUARTERS = ["Q1", "Q2", "Q3", "Q4"]

# Pre-compute per-product totals for the KPI and detail panels
PRODUCT_TOTALS = {row["Product"]: sum(row[q] for q in QUARTERS) for _, row in SALES.iterrows()}
GRAND_TOTAL = sum(PRODUCT_TOTALS.values())
BEST_PRODUCT = max(PRODUCT_TOTALS, key=PRODUCT_TOTALS.get)
BEST_QUARTER = max(QUARTERS, key=lambda q: int(SALES[q].sum()))
AVG_PER_PRODUCT = GRAND_TOTAL // len(SALES)

# ---------------------------------------------------------------------------
# Plotly figure builder
# ---------------------------------------------------------------------------

# Current chart type — mutated by the toolbar callback
_chart_type = "bar"


def make_figure(
    chart_type: str = "bar",
    products: list[str] | None = None,
) -> go.Figure:
    """Build a Plotly figure, optionally limited to *products*."""
    df = SALES if products is None else SALES[SALES["Product"].isin(products)]
    fig = go.Figure()
    for q in QUARTERS:
        trace_cls = go.Bar if chart_type == "bar" else go.Scatter
        kwargs: dict = {"x": df["Product"], "y": df[q], "name": q}
        if chart_type == "line":
            kwargs["mode"] = "lines+markers"
        fig.add_trace(trace_cls(**kwargs))
    fig.update_layout(
        title="Quarterly Sales by Product",
        xaxis_title="Product",
        yaxis_title="Revenue ($)",
        barmode="group" if chart_type == "bar" else None,
        margin={"l": 60, "r": 20, "t": 50, "b": 40},
        legend={"orientation": "h", "y": -0.18},
        template="plotly_dark",
    )
    fig_dict = json.loads(fig.to_json())
    fig_dict["config"] = {"displayModeBar": False}

    return fig_dict


# ---------------------------------------------------------------------------
# Dashboard CSS — uses PyWry theme variables so it auto-matches
# ---------------------------------------------------------------------------

DASHBOARD_CSS = """
.dashboard {
    display: flex;
    flex-direction: column;
    height: 100%;
    gap: 8px;
    padding: 10px;
    overflow-y: auto;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* ---- KPI row ---- */
.kpi-row {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
}
.kpi-card {
    flex: 1;
    background: var(--pywry-bg-tertiary);
    border: 1px solid var(--pywry-border-color);
    border-radius: 6px;
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    gap: 2px;
}
.kpi-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--pywry-text-secondary);
}
.kpi-value {
    font-size: 22px;
    font-weight: 600;
    color: var(--pywry-text-primary);
}

/* ---- Main content row (chart + grid side-by-side) ---- */
.content-row {
    display: flex;
    gap: 8px;
    flex: 1;
    min-height: 0;
}
.panel {
    background: var(--pywry-bg-tertiary);
    border: 1px solid var(--pywry-border-color);
    border-radius: 6px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}
.panel-header {
    padding: 8px 12px;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    color: var(--pywry-text-secondary);
    border-bottom: 1px solid var(--pywry-border-color);
    flex-shrink: 0;
}
.panel-body {
    flex: 1;
    min-height: 0;
    position: relative;
}
.chart-panel { flex: 55; }
.grid-panel  { flex: 45; }

/* Plotly container fills its panel */
.chart-panel .panel-body {
    padding: 6px 8px;
}
.chart-panel .panel-body .pywry-plotly {
    width: 100% !important;
    height: 100% !important;
}

/* Grid container fills its panel */
.grid-panel .panel-body {
    display: flex;
    flex-direction: column;
    padding: 6px 8px;
}
.grid-panel .panel-body .pywry-grid {
    flex: 1;
}

/* ---- Detail panel ---- */
.detail-panel {
    flex-shrink: 0;
    min-height: 60px;
}
.detail-body {
    padding: 10px 14px;
    display: flex;
    gap: 20px;
    align-items: center;
    color: var(--pywry-text-secondary);
    font-size: 13px;
}
.detail-body .detail-product {
    font-size: 15px;
    font-weight: 600;
    color: var(--pywry-text-primary);
    min-width: 90px;
}
.detail-body .detail-metric {
    display: flex;
    flex-direction: column;
    gap: 1px;
}
.detail-body .detail-metric .metric-label {
    font-size: 10px;
    text-transform: uppercase;
    color: var(--pywry-text-muted);
}
.detail-body .detail-metric .metric-value {
    font-size: 14px;
    font-weight: 500;
    color: var(--pywry-text-primary);
}
"""

# ---------------------------------------------------------------------------
# Build the HTML snippets via library integrations
# ---------------------------------------------------------------------------

chart_html = build_plotly_init_script(
    figure=make_figure("bar"),
    chart_id="sales-chart",
)

grid_config = build_grid_config(
    SALES,
    grid_id="sales-grid",
    row_selection=True,
)
grid_html = build_grid_html(grid_config)


def _fmt(n: int) -> str:
    """Format an integer with $ and comma grouping."""
    return f"${n:,}"


DETAIL_PLACEHOLDER = (
    '<span style="color:var(--pywry-text-muted)">'
    "Click a chart bar to see product details, "
    "or select grid rows to filter the chart."
    "</span>"
)

dashboard_html = f"""
<div class="dashboard">
    <!-- KPI cards -->
    <div class="kpi-row">
        <div class="kpi-card">
            <span class="kpi-label">Total Revenue</span>
            <span class="kpi-value">{_fmt(GRAND_TOTAL)}</span>
        </div>
        <div class="kpi-card">
            <span class="kpi-label">Best Product</span>
            <span class="kpi-value">{BEST_PRODUCT}</span>
        </div>
        <div class="kpi-card">
            <span class="kpi-label">Best Quarter</span>
            <span class="kpi-value">{BEST_QUARTER}</span>
        </div>
        <div class="kpi-card">
            <span class="kpi-label">Avg / Product</span>
            <span class="kpi-value">{_fmt(AVG_PER_PRODUCT)}</span>
        </div>
    </div>

    <!-- Chart + Grid side-by-side -->
    <div class="content-row">
        <div class="panel chart-panel">
            <div class="panel-header">Revenue Chart</div>
            <div class="panel-body">{chart_html}</div>
        </div>
        <div class="panel grid-panel">
            <div class="panel-header">Sales Data</div>
            <div class="panel-body">{grid_html}</div>
        </div>
    </div>

    <!-- Detail panel -->
    <div class="panel detail-panel">
        <div class="panel-header">Details</div>
        <div class="detail-body" id="detail-content">{DETAIL_PLACEHOLDER}</div>
    </div>
</div>
"""

# ---------------------------------------------------------------------------
# Toolbar
# ---------------------------------------------------------------------------

toolbar = Toolbar(
    position="top",
    items=[
        Select(
            label="Chart Type:",
            event="app:chart-type",
            options=[
                Option(label="Bar", value="bar"),
                Option(label="Line", value="line"),
            ],
            selected="bar",
        ),
        Button(label="Export CSV", event="app:export", variant="secondary"),
        Button(label="Clear Selection", event="app:clear", variant="ghost"),
    ],
)

# ---------------------------------------------------------------------------
# App + callbacks
# ---------------------------------------------------------------------------

app = PyWry(title="Multi-Widget Demo", theme=ThemeMode.DARK, width=1400, height=780)
widget = None  # assigned after show()

# Track the current selection so chart-type changes preserve it
_selected_products: list[str] = []


def _push_figure(products: list[str] | None = None) -> None:
    """Rebuild the chart figure and send it to the frontend."""
    fig = make_figure(_chart_type, products or None)
    widget.emit(
        "plotly:update-figure",
        {"figure": fig, "chartId": "sales-chart"},
    )


def _push_detail_for_product(name: str) -> None:
    """Update the detail panel with a single product's quarterly breakdown."""
    row = SALES[SALES["Product"] == name].iloc[0]
    total = sum(int(row[q]) for q in QUARTERS)
    best_q = max(QUARTERS, key=lambda q: int(row[q]))
    metrics = "".join(
        f'<div class="detail-metric">'
        f'<span class="metric-label">{q}</span>'
        f'<span class="metric-value">{_fmt(int(row[q]))}</span>'
        f"</div>"
        for q in QUARTERS
    )
    html = (
        f'<span class="detail-product">{name}</span>'
        f"{metrics}"
        f'<div class="detail-metric">'
        f'<span class="metric-label">Total</span>'
        f'<span class="metric-value">{_fmt(total)}</span>'
        f"</div>"
        f'<div class="detail-metric">'
        f'<span class="metric-label">Best Qtr</span>'
        f'<span class="metric-value">{best_q}</span>'
        f"</div>"
    )
    widget.emit("pywry:set-content", {"id": "detail-content", "html": html})


def _push_detail_for_selection(products: list[str]) -> None:
    """Update the detail panel with aggregated stats for selected products."""
    if not products:
        widget.emit(
            "pywry:set-content",
            {"id": "detail-content", "html": DETAIL_PLACEHOLDER},
        )
        return
    if len(products) == 1:
        _push_detail_for_product(products[0])
        return
    subset = SALES[SALES["Product"].isin(products)]
    total = sum(int(subset[q].sum()) for q in QUARTERS)
    metrics = "".join(
        f'<div class="detail-metric">'
        f'<span class="metric-label">{q}</span>'
        f'<span class="metric-value">{_fmt(int(subset[q].sum()))}</span>'
        f"</div>"
        for q in QUARTERS
    )
    html = (
        f'<span class="detail-product">{len(products)} selected</span>'
        f"{metrics}"
        f'<div class="detail-metric">'
        f'<span class="metric-label">Total</span>'
        f'<span class="metric-value">{_fmt(total)}</span>'
        f"</div>"
    )
    widget.emit("pywry:set-content", {"id": "detail-content", "html": html})


# --- Event handlers -------------------------------------------------------


def on_chart_click(data, _event_type, _label):
    """Click a chart data point → show that product's breakdown in detail panel."""
    points = data.get("points", [])
    if points:
        product = points[0].get("x")
        if product:
            _push_detail_for_product(product)


def on_row_selected(data, _event_type, _label):
    """Grid row selection → filter chart to selected products + update detail."""
    global _selected_products  # noqa: PLW0603
    rows = data.get("rows", [])
    _selected_products = [r["Product"] for r in rows if "Product" in r]
    _push_figure(_selected_products or None)
    _push_detail_for_selection(_selected_products)


def on_chart_type(data, _event_type, _label):
    """Toolbar chart-type selector → redraw chart (preserving row selection)."""
    global _chart_type  # noqa: PLW0603
    _chart_type = data.get("value", "bar")
    _push_figure(_selected_products or None)


def on_export(_data, _event_type, _label):
    """Toolbar export → CSV download via the event system."""
    widget.emit(
        "pywry:download",
        {
            "content": SALES.to_csv(index=False),
            "filename": "sales_data.csv",
            "mimeType": "text/csv",
        },
    )


def on_clear(_data, _event_type, _label):
    """Toolbar clear → reset chart, deselect grid rows, clear detail."""
    global _selected_products  # noqa: PLW0603
    _selected_products = []
    _push_figure()
    # Re-set the same data to clear AG Grid's row selection state
    widget.emit(
        "grid:update-data",
        {"data": SALES.to_dict("records"), "gridId": "sales-grid"},
    )
    widget.emit(
        "pywry:set-content",
        {"id": "detail-content", "html": DETAIL_PLACEHOLDER},
    )


# ---------------------------------------------------------------------------
# Show everything in one window
# ---------------------------------------------------------------------------

content = HtmlContent(html=dashboard_html, inline_css=DASHBOARD_CSS)

widget = app.show(
    content,
    include_plotly=True,
    include_aggrid=True,
    toolbars=[toolbar],
    callbacks={
        "plotly:click": on_chart_click,
        "grid:row-selected": on_row_selected,
        "app:chart-type": on_chart_type,
        "app:export": on_export,
        "app:clear": on_clear,
    },
)

app.block()
