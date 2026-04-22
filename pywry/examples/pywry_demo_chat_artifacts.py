"""PyWry Chat Artifacts Demo — render rich content inline in chat.

Demonstrates all 7 artifact types yielded from a ChatManager handler:
  - CodeArtifact       — syntax-highlighted code blocks
  - MarkdownArtifact   — rendered Markdown content
  - HtmlArtifact       — raw HTML in a sandboxed iframe
  - TableArtifact      — interactive AG Grid table (lazy-loaded)
  - PlotlyArtifact     — interactive Plotly chart (lazy-loaded)
  - ImageArtifact      — inline image from URL or data URI
  - JsonArtifact       — collapsible JSON tree viewer

Run::

    python pywry_demo_chat_artifacts.py
"""

from __future__ import annotations

import time

from typing import Any

from pywry import (
    Button,
    CodeArtifact,
    Div,
    HtmlArtifact,
    HtmlContent,
    ImageArtifact,
    JsonArtifact,
    MarkdownArtifact,
    PlotlyArtifact,
    PyWry,
    TableArtifact,
    Toolbar,
)
from pywry.chat.manager import ChatManager
from pywry.chat.models import ACPCommand


# ---------------------------------------------------------------------------
# Sample data for each artifact type
# ---------------------------------------------------------------------------

SAMPLE_CODE = '''\
import asyncio
from dataclasses import dataclass


@dataclass
class Sensor:
    """Represents a single IoT sensor reading."""
    device_id: str
    temperature: float
    humidity: float
    timestamp: float


async def poll_sensors(ids: list[str]) -> list[Sensor]:
    """Poll multiple sensors concurrently."""
    async def _read(dev_id: str) -> Sensor:
        await asyncio.sleep(0.1)  # simulate I/O
        return Sensor(
            device_id=dev_id,
            temperature=22.5 + hash(dev_id) % 10,
            humidity=45.0 + hash(dev_id) % 30,
            timestamp=asyncio.get_event_loop().time(),
        )
    return await asyncio.gather(*[_read(i) for i in ids])


async def main():
    readings = await poll_sensors(["sensor-A", "sensor-B", "sensor-C"])
    for r in readings:
        log.info("%s: %.1f°C, %.0f%%", r.device_id, r.temperature, r.humidity)

asyncio.run(main())
'''

SAMPLE_MARKDOWN = """\
# Project Status Report

## Summary

The **Q1 migration** is on track. Key milestones:

| Milestone          | Status       | ETA        |
|--------------------|-------------|------------|
| Database migration | ✅ Complete  | —          |
| API v2 rollout     | 🔄 In progress | March 25  |
| Frontend redesign  | 📋 Planned  | April 10   |

## Highlights

- Migrated **14 tables** with zero downtime
- New REST endpoints serving `2.1x` faster than v1
- Design system tokens finalized — see [Figma](https://figma.com)

## Next Steps

1. Complete rate-limiting middleware
2. Run load tests against staging
3. Cut release candidate `v2.0.0-rc.1`

> _"Shipping is a feature."_ — Jez Humble
"""

SAMPLE_HTML = """\
<div style="font-family: system-ui; padding: 20px; background: linear-gradient(135deg, #667eea, #764ba2); color: white; border-radius: 12px; text-align: center;">
  <h2 style="margin: 0 0 12px;">Live Dashboard</h2>
  <div style="display: flex; gap: 16px; justify-content: center; flex-wrap: wrap;">
    <div style="background: rgba(255,255,255,0.15); border-radius: 8px; padding: 16px 24px;">
      <div style="font-size: 28px; font-weight: bold;">1,247</div>
      <div style="font-size: 12px; opacity: 0.8;">Active Users</div>
    </div>
    <div style="background: rgba(255,255,255,0.15); border-radius: 8px; padding: 16px 24px;">
      <div style="font-size: 28px; font-weight: bold;">99.97%</div>
      <div style="font-size: 12px; opacity: 0.8;">Uptime</div>
    </div>
    <div style="background: rgba(255,255,255,0.15); border-radius: 8px; padding: 16px 24px;">
      <div style="font-size: 28px; font-weight: bold;">42ms</div>
      <div style="font-size: 12px; opacity: 0.8;">Avg Latency</div>
    </div>
  </div>
</div>
"""

SAMPLE_TABLE_DATA = [
    {
        "Symbol": "AAPL",
        "Price": 189.84,
        "Change": 2.31,
        "Change%": 1.23,
        "Volume": "52.1M",
        "MarketCap": "2.95T",
    },
    {
        "Symbol": "MSFT",
        "Price": 425.22,
        "Change": -1.05,
        "Change%": -0.25,
        "Volume": "18.3M",
        "MarketCap": "3.16T",
    },
    {
        "Symbol": "GOOGL",
        "Price": 175.98,
        "Change": 3.67,
        "Change%": 2.13,
        "Volume": "24.7M",
        "MarketCap": "2.18T",
    },
    {
        "Symbol": "AMZN",
        "Price": 201.45,
        "Change": 0.89,
        "Change%": 0.44,
        "Volume": "31.5M",
        "MarketCap": "2.10T",
    },
    {
        "Symbol": "NVDA",
        "Price": 138.07,
        "Change": 5.42,
        "Change%": 4.09,
        "Volume": "87.2M",
        "MarketCap": "3.39T",
    },
    {
        "Symbol": "META",
        "Price": 612.77,
        "Change": -3.18,
        "Change%": -0.52,
        "Volume": "12.8M",
        "MarketCap": "1.56T",
    },
    {
        "Symbol": "TSLA",
        "Price": 248.42,
        "Change": 8.91,
        "Change%": 3.72,
        "Volume": "65.4M",
        "MarketCap": "791B",
    },
    {
        "Symbol": "BRK.B",
        "Price": 457.30,
        "Change": 0.15,
        "Change%": 0.03,
        "Volume": "3.1M",
        "MarketCap": "1.05T",
    },
]

SAMPLE_PLOTLY_FIGURE = {
    "data": [
        {
            "type": "scatter",
            "mode": "lines+markers",
            "name": "Revenue",
            "x": ["Q1 '24", "Q2 '24", "Q3 '24", "Q4 '24", "Q1 '25", "Q2 '25"],
            "y": [42, 49, 53, 61, 58, 72],
            "line": {"color": "#667eea", "width": 3},
            "marker": {"size": 8},
        },
        {
            "type": "bar",
            "name": "Expenses",
            "x": ["Q1 '24", "Q2 '24", "Q3 '24", "Q4 '24", "Q1 '25", "Q2 '25"],
            "y": [38, 41, 44, 47, 45, 50],
            "marker": {"color": "rgba(118, 75, 162, 0.6)"},
        },
    ],
    "layout": {
        "title": {"text": "Revenue vs Expenses ($M)", "font": {"size": 16}},
        "xaxis": {"title": "Quarter"},
        "yaxis": {"title": "Amount ($M)"},
        "legend": {"orientation": "h", "y": -0.2},
        "margin": {"t": 50, "b": 60, "l": 60, "r": 20},
        "plot_bgcolor": "rgba(0,0,0,0)",
        "paper_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": "#e0e0e0"},
    },
    "config": {"responsive": True, "displayModeBar": False},
}

# 1x1 transparent PNG as a data URI for a safe inline demo
SAMPLE_IMAGE_URL = (
    "data:image/svg+xml;base64,"
    "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIy"
    "ODAiIGhlaWdodD0iMjAwIiB2aWV3Qm94PSIwIDAgMjgwIDIwMCI+PGRlZnM+PGxp"
    "bmVhckdyYWRpZW50IGlkPSJnIiB4MT0iMCUiIHkxPSIwJSIgeDI9IjEwMCUiIHky"
    "PSIxMDAlIj48c3RvcCBvZmZzZXQ9IjAlIiBzdG9wLWNvbG9yPSIjNjY3ZWVhIi8+"
    "PHN0b3Agb2Zmc2V0PSIxMDAlIiBzdG9wLWNvbG9yPSIjNzY0YmEyIi8+PC9saW5l"
    "YXJHcmFkaWVudD48L2RlZnM+PHJlY3Qgd2lkdGg9IjI4MCIgaGVpZ2h0PSIyMDAi"
    "IHJ4PSIxMiIgZmlsbD0idXJsKCNnKSIvPjx0ZXh0IHg9IjUwJSIgeT0iNDUlIiBk"
    "b21pbmFudC1iYXNlbGluZT0ibWlkZGxlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBm"
    "aWxsPSJ3aGl0ZSIgZm9udC1mYW1pbHk9InN5c3RlbS11aSIgZm9udC1zaXplPSIy"
    "NCI+8J+WvO+4jyBTYW1wbGUgSW1hZ2U8L3RleHQ+PHRleHQgeD0iNTAlIiB5PSI2"
    "MCUiIGRvbWluYW50LWJhc2VsaW5lPSJtaWRkbGUiIHRleHQtYW5jaG9yPSJtaWRk"
    "bGUiIGZpbGw9InJnYmEoMjU1LDI1NSwyNTUsMC43KSIgZm9udC1mYW1pbHk9InN5"
    "c3RlbS11aSIgZm9udC1zaXplPSIxNCI+SW1hZ2VBcnRpZmFjdCBEZW1vPC90ZXh0"
    "Pjwvc3ZnPg=="
)

SAMPLE_JSON = {
    "apiVersion": "v2",
    "request": {
        "id": "req_8f3a2b1c",
        "timestamp": "2025-03-18T14:30:00Z",
        "method": "POST",
        "endpoint": "/api/v2/analyze",
    },
    "response": {
        "status": 200,
        "data": {
            "sentiment": "positive",
            "confidence": 0.94,
            "entities": [
                {"text": "PyWry", "type": "PRODUCT", "score": 0.99},
                {"text": "Python", "type": "LANGUAGE", "score": 0.97},
            ],
            "tokens_used": 1247,
        },
        "metadata": {"model": "gpt-4", "latency_ms": 342},
    },
}


# ---------------------------------------------------------------------------
# Handler — yields artifacts based on user message or slash commands
# ---------------------------------------------------------------------------


def _yield_code():
    """Yield code artifact for 'code' keyword."""
    yield "Here's an **async IoT sensor polling** example:\n\n"
    time.sleep(0.3)
    yield CodeArtifact(title="sensor_reader.py", content=SAMPLE_CODE, language="python")
    yield "\nThe code uses `asyncio.gather` for concurrent I/O."


def _yield_markdown():
    """Yield markdown artifact for 'markdown'/'report' keyword."""
    yield "Here's the latest project status report:\n\n"
    time.sleep(0.3)
    yield MarkdownArtifact(title="Q1 Status Report", content=SAMPLE_MARKDOWN)
    yield "\nAll sections rendered with full Markdown formatting."


def _yield_html():
    """Yield HTML artifact for 'html'/'dashboard' keyword."""
    yield "Rendering a **live dashboard** widget:\n\n"
    time.sleep(0.3)
    yield HtmlArtifact(title="Dashboard Widget", content=SAMPLE_HTML)
    yield "\nThe HTML runs inside a sandboxed iframe for safety."


def _yield_table():
    """Yield table artifact for 'table'/'stock'/'grid' keyword."""
    yield "Loading **market data** into an AG Grid table:\n\n"
    time.sleep(0.3)
    yield TableArtifact(title="Market Overview", data=SAMPLE_TABLE_DATA, height="320px")
    yield "\nClick column headers to sort. The grid supports filtering too."


def _yield_plotly():
    """Yield Plotly artifact for 'chart'/'plotly'/'graph' keyword."""
    yield "Generating a **revenue vs expenses** chart:\n\n"
    time.sleep(0.3)
    yield PlotlyArtifact(title="Financial Overview", figure=SAMPLE_PLOTLY_FIGURE, height="380px")
    yield "\nHover over data points for details. The chart is fully interactive."


def _yield_image():
    """Yield image artifact for 'image'/'picture'/'photo' keyword."""
    yield "Here's a sample image artifact:\n\n"
    time.sleep(0.3)
    yield ImageArtifact(
        title="PNG Transparency Demo",
        url=SAMPLE_IMAGE_URL,
        alt="PNG transparency demonstration - checkerboard pattern",
    )
    yield "\nImages can use HTTPS URLs or inline `data:` URIs."


def _yield_json():
    """Yield JSON artifact for 'json'/'api'/'data' keyword."""
    yield "Here's a sample API response payload:\n\n"
    time.sleep(0.3)
    yield JsonArtifact(title="API Response", data=SAMPLE_JSON)
    yield "\nExpand/collapse nested objects to explore the structure."


def _yield_all():
    """Yield all 7 artifact types at once."""
    yield "Rendering **all 7 artifact types** in a single response:\n\n"
    time.sleep(0.2)

    yield "### 1. Code\n"
    yield CodeArtifact(title="sensor_reader.py", content=SAMPLE_CODE, language="python")
    time.sleep(0.2)

    yield "\n### 2. Markdown\n"
    yield MarkdownArtifact(title="Q1 Status Report", content=SAMPLE_MARKDOWN)
    time.sleep(0.2)

    yield "\n### 3. HTML\n"
    yield HtmlArtifact(title="Dashboard Widget", content=SAMPLE_HTML)
    time.sleep(0.2)

    yield "\n### 4. Table (AG Grid)\n"
    yield TableArtifact(title="Market Overview", data=SAMPLE_TABLE_DATA, height="320px")
    time.sleep(0.2)

    yield "\n### 5. Chart (Plotly)\n"
    yield PlotlyArtifact(title="Financial Overview", figure=SAMPLE_PLOTLY_FIGURE, height="380px")
    time.sleep(0.2)

    yield "\n### 6. Image\n"
    yield ImageArtifact(title="PNG Demo", url=SAMPLE_IMAGE_URL, alt="Transparency demo")
    time.sleep(0.2)

    yield "\n### 7. JSON\n"
    yield JsonArtifact(title="API Response", data=SAMPLE_JSON)

    yield "\n\nThat covers every artifact type! 🎉"


# Keyword-to-handler dispatch table
_ARTIFACT_KEYWORDS: list[tuple[list[str], Any]] = [
    (["code"], _yield_code),
    (["markdown", "report"], _yield_markdown),
    (["html", "dashboard"], _yield_html),
    (["table", "stock", "grid"], _yield_table),
    (["chart", "plotly", "graph"], _yield_plotly),
    (["image", "picture", "photo"], _yield_image),
    (["json", "api", "data"], _yield_json),
    (["all", "everything", "demo"], _yield_all),
]


def artifact_handler(messages, ctx):
    """Demonstrate every artifact type based on keywords or slash commands."""
    user_text = messages[-1]["text"].strip().lower()

    for keywords, handler_fn in _ARTIFACT_KEYWORDS:
        if any(kw in user_text for kw in keywords):
            yield from handler_fn()
            return

    # ── Default: list available commands ───────────────────────────
    yield (
        "I can render different artifact types. Try one of these:\n\n"
        "- **code** — syntax-highlighted code block\n"
        "- **markdown** or **report** — rendered Markdown\n"
        "- **html** or **dashboard** — sandboxed HTML widget\n"
        "- **table** or **stock** — AG Grid data table\n"
        "- **chart** or **plotly** — interactive Plotly chart\n"
        "- **image** — inline image\n"
        "- **json** or **api** — collapsible JSON tree\n"
        "- **all** — render every artifact type at once\n\n"
        "Or use the slash commands: `/code`, `/markdown`, `/html`, "
        "`/table`, `/chart`, `/image`, `/json`, `/all`"
    )


def on_slash(command, args, thread_id):
    """Dispatch slash commands by simulating a user message through the handler."""
    keyword_map = {
        "/code": "code",
        "/markdown": "markdown",
        "/html": "html",
        "/table": "table",
        "/chart": "chart",
        "/image": "image",
        "/json": "json",
        "/all": "all",
    }
    keyword = keyword_map.get(command)
    if keyword:
        chat._on_user_message(
            {"text": keyword, "threadId": thread_id},
            "",
            "",
        )


# ---------------------------------------------------------------------------
# ChatManager — declarative configuration
# ---------------------------------------------------------------------------

chat = ChatManager(
    handler=artifact_handler,
    include_plotly=True,
    include_aggrid=True,
    welcome_message=(
        "Welcome to the **Artifact Rendering Demo**!\n\n"
        "Type a keyword or use a slash command to see rich artifacts inline:\n\n"
        "| Command | Artifact Type |\n"
        "|---------|---------------|\n"
        "| `/code` | Syntax-highlighted code |\n"
        "| `/markdown` | Rendered Markdown |\n"
        "| `/html` | Sandboxed HTML widget |\n"
        "| `/table` | AG Grid data table |\n"
        "| `/chart` | Interactive Plotly chart |\n"
        "| `/image` | Inline image |\n"
        "| `/json` | Collapsible JSON tree |\n"
        "| `/all` | All types at once |\n\n"
        "Or just type **code**, **chart**, **table**, etc."
    ),
    slash_commands=[
        ACPCommand(name="/code", description="Show a code artifact"),
        ACPCommand(name="/markdown", description="Show a Markdown artifact"),
        ACPCommand(name="/html", description="Show an HTML artifact"),
        ACPCommand(name="/table", description="Show an AG Grid table"),
        ACPCommand(name="/chart", description="Show a Plotly chart"),
        ACPCommand(name="/image", description="Show an image artifact"),
        ACPCommand(name="/json", description="Show a JSON tree artifact"),
        ACPCommand(name="/all", description="Render all 7 artifact types"),
    ],
    on_slash_command=on_slash,
    toolbar_width="420px",
)


# ---------------------------------------------------------------------------
# Main page content — composed with PyWry Div components
# ---------------------------------------------------------------------------

ARTIFACT_TYPES = [
    ("<strong>CodeArtifact</strong>", "Syntax-highlighted code blocks"),
    ("<strong>MarkdownArtifact</strong>", "Rendered Markdown with tables and lists"),
    ("<strong>HtmlArtifact</strong>", "Raw HTML in a sandboxed iframe"),
    ("<strong>TableArtifact</strong>", "Interactive AG Grid (lazy-loaded)"),
    ("<strong>PlotlyArtifact</strong>", "Interactive Plotly charts (lazy-loaded)"),
    ("<strong>ImageArtifact</strong>", "Inline images via URL or data URI"),
    ("<strong>JsonArtifact</strong>", "Collapsible JSON tree viewer"),
]

main_content = Div(
    event="app:main",
    style=("padding: 24px; font-family: var(--pywry-font-family); overflow-y: auto; height: 100%;"),
    children=[
        Div(
            event="app:header",
            content=(
                '<h1 style="margin: 0 0 16px; color: var(--pywry-text-primary);">'
                "Artifact Rendering Demo</h1>"
                '<p style="color: var(--pywry-text-secondary); margin: 0 0 16px;'
                ' line-height: 1.6;">'
                "This demo showcases <strong>all 7 artifact types</strong> that "
                "ChatManager handlers can yield. Artifacts render as standalone "
                "rich blocks in the chat — tables, charts, code, images, and more."
                "</p>"
            ),
        ),
        Div(
            event="app:types",
            style=(
                "background: var(--pywry-bg-tertiary);"
                " border: 1px solid var(--pywry-border-color);"
                " border-radius: 8px; padding: 16px; margin-bottom: 16px;"
            ),
            content=(
                '<h3 style="margin: 0 0 8px; font-size: 14px;'
                ' color: var(--pywry-text-primary);">'
                "Available Artifact Types:</h3>"
                '<ul style="margin: 0; padding-left: 20px;'
                ' color: var(--pywry-text-secondary); line-height: 1.8;">'
                + "".join(f"<li>{name} — {desc}</li>" for name, desc in ARTIFACT_TYPES)
                + "</ul>"
            ),
        ),
        Div(
            event="app:hint",
            style=(
                "background: var(--pywry-bg-secondary);"
                " border-left: 3px solid var(--pywry-accent-color);"
                " border-radius: 4px; padding: 12px 16px;"
            ),
            content=(
                '<p style="margin: 0; color: var(--pywry-text-secondary);'
                ' font-size: 13px;">'
                "💡 <strong>Tip:</strong> Type <code>all</code> or use "
                "<code>/all</code> to render every artifact type in a single "
                "response."
                "</p>"
            ),
        ),
    ],
)

app = PyWry(title="Artifact Demo", width=1200, height=750)
content = HtmlContent(html=main_content.build_html())

top_toolbar = Toolbar(
    position="top",
    items=[
        Button(label="Clear Chat", event="app:clear-chat", variant="secondary"),
    ],
)


def on_clear_chat(_data, _event_type, _label):
    """Clear chat messages and thread history."""
    chat._emit("chat:clear", {})
    chat._threads[chat.active_thread_id] = []


widget = app.show(
    content,
    toolbars=[top_toolbar, chat.toolbar()],
    callbacks={
        **chat.callbacks(),
        "app:clear-chat": on_clear_chat,
    },
)
chat.bind(widget)
app.block()
