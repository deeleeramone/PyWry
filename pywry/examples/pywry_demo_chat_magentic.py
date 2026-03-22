"""PyWry + Magentic Chat Demo — Gemini-powered data analyst.

Shows a Plotly chart + AG Grid table in the main panel with a ChatManager
sidebar.  Dashboard components are registered as @-mentionable context
sources.  The LLM manages its own context via the ``get_context`` tool.

Key concepts demonstrated:

  • ``register_context_source(component_id, name)`` — real components
  • ``CONTEXT_TOOL`` — LLM calls tools to read attached component data
  • Frontend extracts live data from the grid/chart at send time

Run::

    python pywry_demo_magentic.py
"""

from __future__ import annotations

import json
import os

import pandas as pd
import plotly.graph_objects as go

from magentic import (
    AssistantMessage,
    AsyncStreamedStr,
    Chat,
    FunctionCall,
    OpenaiChatModel,
    SystemMessage,
    UserMessage,
)
from magentic.chat_model.message import FunctionResultMessage

from pywry import HtmlContent, PyWry, ThemeMode
from pywry.chat_manager import ChatManager, ToolCallResponse, ToolResultResponse
from pywry.grid import build_grid_config, build_grid_html
from pywry.templates import build_plotly_init_script


# ---------------------------------------------------------------------------
# Gemini configuration
# ---------------------------------------------------------------------------

GEMINI_API_KEY = os.environ.get(
    "GEMINI_API_KEY",
    ""
)

gemini_model = OpenaiChatModel(
    "gemini-2.5-flash",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    api_key=GEMINI_API_KEY,
)


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

PRODUCT_TOTALS = {row["Product"]: sum(row[q] for q in QUARTERS) for _, row in SALES.iterrows()}
GRAND_TOTAL = sum(PRODUCT_TOTALS.values())
BEST_PRODUCT = max(PRODUCT_TOTALS, key=PRODUCT_TOTALS.get)
BEST_QUARTER = max(QUARTERS, key=lambda q: int(SALES[q].sum()))
AVG_PER_PRODUCT = GRAND_TOTAL // len(SALES)


# ---------------------------------------------------------------------------
# Plotly figure builder
# ---------------------------------------------------------------------------


def make_figure() -> dict:
    """Build a grouped bar chart of quarterly sales."""
    fig = go.Figure()
    for q in QUARTERS:
        fig.add_trace(go.Bar(x=SALES["Product"], y=SALES[q], name=q))
    fig.update_layout(
        title="Quarterly Sales by Product",
        xaxis_title="Product",
        yaxis_title="Revenue ($)",
        barmode="group",
        margin={"l": 60, "r": 20, "t": 50, "b": 40},
        legend={"orientation": "h", "y": -0.18},
        template="plotly_dark",
    )
    fig_dict = json.loads(fig.to_json())
    fig_dict["config"] = {"displayModeBar": False}
    return fig_dict


# ---------------------------------------------------------------------------
# Dashboard CSS
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
.chart-panel .panel-body { padding: 6px 8px; }
.chart-panel .panel-body .pywry-plotly {
    width: 100% !important;
    height: 100% !important;
}
.grid-panel .panel-body {
    display: flex;
    flex-direction: column;
    padding: 6px 8px;
}
.grid-panel .panel-body .pywry-grid { flex: 1; }
"""


# ---------------------------------------------------------------------------
# Build HTML
# ---------------------------------------------------------------------------

chart_html = build_plotly_init_script(figure=make_figure(), chart_id="sales-chart")
grid_config = build_grid_config(SALES, grid_id="sales-grid")
grid_html = build_grid_html(grid_config)


def _fmt(n: int) -> str:
    return f"${n:,}"


dashboard_html = f"""
<div class="dashboard">
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
</div>
"""


# ---------------------------------------------------------------------------
# Chat handler — LLM manages context via tool calls
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a data analyst assistant. A quarterly sales dashboard is displayed
next to this chat with a revenue chart and a data grid.

The user can attach dashboard components or files using @ or drag-and-drop.
When attachments are present they will be included in the message text
automatically — never guess data, always read the attached content first.

Be concise but thorough. Use markdown formatting.\
"""


async def handler(messages: list[dict], ctx):
    """Stream responses from Gemini, using tools to read attached context."""
    # Build tool list — add get_context when attachments are present
    tools: list = []
    if ctx.attachments:

        def get_context(name: str) -> str:
            """Read the content of an attached dashboard component or file."""
            att = next(
                (
                    a
                    for a in ctx.attachments
                    if a.name.lstrip("@").strip() == name.lstrip("@").strip()
                ),
                None,
            )
            if att is None:
                available = ", ".join(a.name for a in ctx.attachments)
                return f"Attachment '{name}' not found. Available: {available}"
            # File attachments — read content from disk
            if att.path:
                return att.path.read_text(encoding="utf-8", errors="replace")
            # Widget attachments — content already extracted
            return att.content

        tools.append(get_context)

    # Convert messages to magentic format
    magentic_msgs = [SystemMessage(ctx.system_prompt)]
    for m in messages:
        text = m.get("text", "")
        if m.get("role") == "user":
            # Tell the LLM what's attached so it knows to call the tool
            if m is messages[-1] and ctx.attachment_summary:
                text = ctx.attachment_summary + "\n\n" + text
            magentic_msgs.append(UserMessage(text))
        else:
            magentic_msgs.append(AssistantMessage(text))

    response = await Chat(
        messages=magentic_msgs,
        model=gemini_model,
        output_types=[AsyncStreamedStr] + ([FunctionCall[str]] if tools else []),
        functions=tools or None,
    ).asubmit()

    # Tool-call loop — LLM calls get_context to read attached data
    while isinstance(response.last_message.content, FunctionCall):
        fn_call = response.last_message.content

        yield ToolCallResponse(name=fn_call.function.__name__, arguments=fn_call.arguments)

        result = fn_call()
        yield ToolResultResponse(
            tool_id="",
            result=result if len(result) <= 300 else result[:300] + "…",
        )

        response = await response.add_message(
            FunctionResultMessage(content=result, function_call=fn_call)
        ).asubmit()

    # Stream the final text response
    async for chunk in response.last_message.content:
        if ctx.cancel_event.is_set():
            return
        yield chunk


# ---------------------------------------------------------------------------
# ChatManager
# ---------------------------------------------------------------------------

chat = ChatManager(
    handler=handler,
    system_prompt=SYSTEM_PROMPT,
    model="gemini-2.5-flash",
    welcome_message=(
        "Hi! I'm your **data analyst** powered by Gemini 2.5 Flash.\n\n"
        "I can see the sales dashboard next to me. Type **@** to attach \n"
        "the **Sales Data** grid or **Revenue Chart** \u2014 I'll read the \n"
        "live data from the component and analyze it.\n\n"
        "You can also **drag-and-drop files** (CSV, JSON, PDF, XLSX, etc.) "
        "into this chat for analysis."
    ),
    toolbar_width="420px",
    toolbar_min_width="320px",
    enable_context=True,
    enable_file_attach=True,
    file_accept_types=[".csv", ".json", ".txt", ".md", ".xlsx", ".pdf"],
    include_plotly=True,
    include_aggrid=True,
)

# Register the actual dashboard components as @-mentionable context sources
chat.register_context_source("sales-grid", "Sales Data")
chat.register_context_source("sales-chart", "Revenue Chart")


# ---------------------------------------------------------------------------
# Launch — dashboard + chat sidebar
# ---------------------------------------------------------------------------

app = PyWry(title="Magentic Data Analyst", theme=ThemeMode.DARK, width=1400, height=780)
content = HtmlContent(html=dashboard_html, inline_css=DASHBOARD_CSS)

widget = app.show(
    content,
    include_plotly=True,
    include_aggrid=True,
    toolbars=[chat.toolbar()],
    callbacks=chat.callbacks(),
)
chat.bind(widget)
app.block()
