"""PyWry LangChain Deep Agent Demo — NVIDIA NIM + TradingView Chart.

An AI-powered financial chart analyst that drives the live chart
exclusively through PyWry's FastMCP tool suite.  There are no local
LangChain tools — every action is an MCP tool served by the in-process
PyWry MCP server.

The TradingView chart (with yFinance datafeed) occupies the main
window area while the Deep Agent chat panel sits in a right-side
toolbar.  The MCP server is started on a random localhost port and
shares the app's widget registry so tool calls drive the live chart.

Usage::

    pip install 'pywry[deepagent,mcp]' yfinance langchain-nvidia-ai-endpoints
    export NVIDIA_API_KEY="nvapi-..."
    python pywry_demo_deepagent_nvidia.py          # AAPL chart
    python pywry_demo_deepagent_nvidia.py MSFT      # MSFT chart
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import pathlib
import socket
import sys
import threading

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from collections.abc import Callable


# Silence the benign Windows ProactorEventLoop close-race tracebacks
# ("Exception in callback _ProactorBasePipeTransport._call_connection_lost
# ... ConnectionResetError: [WinError 10054]") that fire when a remote
# forcibly closes a socket asyncio is mid-shutdown on.  Install on every
# loop created in this process by wrapping the default policy — this
# catches loops in the MCP server thread, the langchain_mcp_adapters
# client connection, PyWry's own runtime, etc.
def _asyncio_exception_handler(loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    exc = context.get("exception")
    if isinstance(exc, (ConnectionResetError, ConnectionAbortedError)):
        return
    msg = str(context.get("message", ""))
    if "WinError 10054" in msg or "forcibly closed" in msg:
        return
    loop.default_exception_handler(context)


class _QuietProactorPolicy(asyncio.DefaultEventLoopPolicy):
    """Event-loop policy that drops proactor close-race tracebacks.

    Pre-installs ``_asyncio_exception_handler`` on every loop created
    so the filter is active before any loop starts running.
    """

    def new_event_loop(self) -> asyncio.AbstractEventLoop:
        loop = super().new_event_loop()
        loop.set_exception_handler(_asyncio_exception_handler)
        return loop


# Install only once, at import time, before any other loop is created.
_existing_policy = asyncio.get_event_loop_policy()
if not isinstance(_existing_policy, _QuietProactorPolicy):
    asyncio.set_event_loop_policy(_QuietProactorPolicy())

from pywry_demo_tvchart_yfinance import (  # noqa: E402  (policy install precedes imports)
    SUPPORTED_RESOLUTIONS,
    BarCache,
    RealtimeStreamer,
    build_marquee,
    make_callbacks,
)

from pywry import PyWry, ThemeMode  # noqa: E402
from pywry.chat.manager import ChatManager, SettingsItem  # noqa: E402
from pywry.chat.providers.deepagent import DeepagentProvider  # noqa: E402
from pywry.tvchart import build_tvchart_toolbars  # noqa: E402


DEFAULT_MODEL = "qwen/qwen3-coder-480b-a35b-instruct"

# Preferred tool-capable chat models exposed through NVIDIA NIM, in
# priority order.  The first model that the live ``ChatNVIDIA.
# get_available_models()`` lookup actually returns is picked as the
# default.  Llama variants are intentionally excluded — they under-
# perform on strict-format tool-calling compared to the models below.
PREFERRED_TOOL_MODELS = [
    "qwen/qwen3-coder-480b-a35b-instruct",
    "deepseek-ai/deepseek-v3.1",
    "deepseek-ai/deepseek-r1",
    "moonshotai/kimi-k2-instruct-0905",
    "openai/gpt-oss-120b",
    "qwen/qwen3-235b-a22b-instruct-2507",
    "zai-org/glm-4.5-air",
    "mistralai/mistral-nemotron",
]

CHART_SYSTEM_PROMPT = """\
You drive a live TradingView chart through MCP tools.

widget_id: read it from the ``widget_id: <id>`` line inside any \
``--- Attached: <name> ---`` block on the user's message.  Pass it \
on every tool call.

For every user request, call the matching tool and reply with ONE \
sentence confirming what changed.  Examples of the complete reply \
(not an excerpt):

    Switched to MSFT on the weekly.
    Added a 50-period SMA.
    Added SPY as a compare series.
    Set the interval to 1m.

Tool → intent:

- Change ticker → tvchart_symbol_search(widget_id, query, auto_select=True)
- Timeframe → tvchart_change_interval(widget_id, value)   (1m 5m 15m 1h 1d 1w 1M ...)
- Chart type → tvchart_chart_type(widget_id, value)   (Candles, Line, Heikin Ashi, Bars, Area)
- Indicator → tvchart_add_indicator(widget_id, name, period=...)
- Compare overlay → tvchart_compare(widget_id, query, auto_add=True)
- Price line → tvchart_add_price_line(widget_id, price, title=...)
- Markers → tvchart_add_markers(widget_id, markers)
- Zoom preset → tvchart_time_range(widget_id, value)   (1D 1W 1M 3M 6M 1Y 5Y YTD)
- Visible range → tvchart_set_visible_range(widget_id, from_time, to_time)
- Fit all → tvchart_fit_content(widget_id)
- Log/auto scale → tvchart_log_scale / tvchart_auto_scale(widget_id, value=bool)
- Undo / redo → tvchart_undo / tvchart_redo(widget_id)
- Screenshot → tvchart_screenshot(widget_id)
- Fullscreen → tvchart_fullscreen(widget_id)
- Remove indicator → tvchart_remove_indicator(widget_id, series_id)
- List indicators → tvchart_list_indicators(widget_id)

Every required argument MUST be set.  Missing ``value`` / ``query`` \
returns an error — do not emit without it.

To report chart state (symbol, interval, indicators, last close, \
visible range, anything): call tvchart_request_state(widget_id) and \
quote exact values from the return.  Never recall from memory, \
earlier turns, or training data.

FORBIDDEN in every reply:

- Headers, sections, ``Current Chart State``, ``Next Steps``, \
  ``Action Summary``, ``Debug Logs``, ``Confirmation``, ``OFFICIAL \
  RESPONSE``, ``FINAL RESPONSE``, or any similar label.
- Multi-choice menus ("Would you like to / Reply with one of").
- Pseudo-JSON, tables, or code blocks quoting tool returns.
- Writing tool calls as prose text.
- Numbers or symbols not present in a real tool return this turn.
- Multiple sentences except when the user explicitly asked for \
  several distinct pieces of information.

Multi-step requests
-------------------

Count the distinct chart actions the user asked for.  Examples:

- "switch to MSFT and go weekly"                       — 2 steps
- "update to BTC-USD, go 1m, zoom to last day"         — 3 steps
- "add a 50 SMA, a 200 SMA, and an RSI"                — 3 steps
- "switch to BTC-USD"                                  — 1 step (skip todos)

If the count is >= 2, follow this flow:

1. Call ``write_todos`` with one entry per step, all in \
   ``pending`` status.  This renders the plan card.

2. For each step in order, issue BOTH tool calls together in the \
   SAME model response (parallel tool calls on one assistant \
   message):

   - the chart tool for the step, AND
   - ``write_todos`` with that step flipped to ``completed``, \
     every prior step kept ``completed``, every remaining step \
     kept ``pending``.

   Issuing them in one response halves the round-trips per step \
   and keeps the plan card in sync with the chart in real time.  \
   Do NOT split them across two turns.

3. After the LAST step's parallel ``chart tool + write_todos`` \
   response has returned, reply with ONE sentence summarising the \
   final state.

You MUST do every step in the SAME turn.  Do not stop after the \
first tool call, do not emit a summary reply before every \
``pending`` step has become ``completed``, do not return control \
to the user mid-plan.

Error handling — FAIL FAST:

If a chart tool returns ``confirmed: false`` or ``error``, STOP \
THE PLAN.  In the next response, call ``write_todos`` alone with \
the failed step marked ``failed`` and every remaining step still \
``pending``, then reply with ONE sentence stating which step \
failed and the tool's ``reason``.  Do NOT attempt the remaining \
steps — they likely depend on the failed one and running them \
blind wastes tool calls and confuses the chart state.

Single-action requests (one tool call) skip ``write_todos`` \
entirely — one tool call, one reply sentence, done.
"""


def _start_pywry_mcp_server(app: PyWry, widget_id: str) -> tuple[str, Callable[[], None]]:
    """Start PyWry's FastMCP server in-process and return ``(url, stop)``.

    The server shares ``pywry.mcp.state._app`` with the running PyWry app
    so MCP tools operate on the live chart widget.

    Drives a ``uvicorn.Server`` directly against the FastMCP Starlette
    app so we have a handle (``server.should_exit``) for graceful
    shutdown.  ``stop()`` sets the flag and joins the owning thread;
    uvicorn then walks through its normal shutdown sequence — close
    listen sockets, wait for active requests, unwind the lifespan task
    group from inside the same task that entered it.  This avoids the
    "attempted to exit cancel scope in a different task" /
    "athrow(): asynchronous generator is already running" errors that
    arise from cancelling a task mid-``anyio.TaskGroup``.
    """
    import uvicorn

    import pywry.mcp.state as mcp_state

    from pywry.mcp.server import create_server
    from pywry.mcp.state import register_widget

    mcp_state._app = app
    register_widget(widget_id, app)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    mcp = create_server()
    starlette_app = mcp.http_app(transport="streamable-http")

    config = uvicorn.Config(
        app=starlette_app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        lifespan="on",
        # Keep shutdown tight — single-client in-process server.
        timeout_graceful_shutdown=2,
    )
    server = uvicorn.Server(config)

    def _thread_target() -> None:
        # The module-level ``_QuietProactorPolicy`` already pre-installs
        # a Windows-proactor close-race filter on every loop we create
        # — no per-thread handler install needed here.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(server.serve())
        finally:
            # Cancel any tasks that uvicorn / starlette / sse_starlette
            # left pending (e.g. ``_shutdown_watcher`` in sse_starlette),
            # then drain them to completion before closing the loop.
            # Otherwise Python emits ``Task was destroyed but it is
            # pending!`` warnings when the loop closes.
            pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
            for task in pending:
                task.cancel()
            if pending:
                with contextlib.suppress(Exception):
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            with contextlib.suppress(Exception):
                loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    thread = threading.Thread(target=_thread_target, name="pywry-mcp-server", daemon=True)
    thread.start()

    # Wait for the server to actually start listening so the agent's
    # first tool call doesn't race startup.
    import time as _time

    deadline = _time.monotonic() + 5.0
    while _time.monotonic() < deadline and not server.started:
        _time.sleep(0.05)

    def stop() -> None:
        # Flip uvicorn's graceful-shutdown flag.  ``server.serve()``
        # polls this each iteration; once set it stops accepting new
        # connections, closes the listen socket, cancels the lifespan
        # task *cooperatively from inside its own task*, waits up to
        # ``timeout_graceful_shutdown`` seconds for active requests to
        # finish, then returns cleanly from serve().  No cross-task
        # cancellation, no stuck async generators.
        server.should_exit = True
        thread.join(timeout=float(config.timeout_graceful_shutdown) + 2.0)

    return f"http://127.0.0.1:{port}/mcp", stop


def _fetch_nvidia_models() -> list[str]:
    """Fetch available tool-capable chat models from NVIDIA NIM."""
    try:
        from langchain_nvidia_ai_endpoints import ChatNVIDIA

        available = ChatNVIDIA.get_available_models()
        model_ids = sorted(
            m.id
            for m in available
            if getattr(m, "model_type", None) == "chat" and getattr(m, "supports_tools", False)
        )
        if not model_ids:
            return [DEFAULT_MODEL]
        for preferred in PREFERRED_TOOL_MODELS:
            if preferred in model_ids:
                model_ids = [preferred, *[m for m in model_ids if m != preferred]]
                break
        if model_ids:
            return model_ids
    except Exception:
        return [DEFAULT_MODEL]


def main() -> None:
    """Launch the NVIDIA Deep Agent + TradingView chart."""
    symbol = sys.argv[1].upper() if len(sys.argv) > 1 else "AAPL"

    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key:
        sys.exit(
            "NVIDIA_API_KEY environment variable is required.\n"
            "Get one at https://build.nvidia.com/ and run:\n"
            "  export NVIDIA_API_KEY='nvapi-...'"
        )

    app = PyWry(theme=ThemeMode.DARK)
    cache = BarCache()
    streamer = RealtimeStreamer(app, cache)

    datafeed_callbacks = make_callbacks(app, streamer, cache)

    model_ids = _fetch_nvidia_models()
    initial_model = model_ids[0] if model_ids else DEFAULT_MODEL

    # "chart" is the user-facing NAME of the TradingView component
    # instance the agent operates on.  It shows up in three places:
    #
    # 1. ``app.show_tvchart(chart_id="chart", ...)`` — assigns the name
    #    to the actual TV component, so every ``chartId`` field on
    #    tvchart events carries it.
    # 2. ``register_widget("chart", app)`` — registers the containing
    #    PyWry widget under the same name for MCP routing.  Single-
    #    widget servers: the MCP handler auto-resolves ``widget_id``
    #    from the sole registered widget; this just labels it.
    # 3. ``chat.register_context_source("chart", ...)`` — exposes the
    #    chart as an ``@chart`` mention in the chat UI.  The attachment
    #    carries the chart component's id, letting the agent route
    #    tvchart_* tool calls against that specific instance.
    CHART_COMPONENT_ID = "chart"
    mcp_url, stop_mcp_server = _start_pywry_mcp_server(app, widget_id=CHART_COMPONENT_ID)
    mcp_servers = {
        "pywry": {"transport": "streamable_http", "url": mcp_url},
    }

    # No local LangChain tools — every action the agent takes is an MCP
    # tool served by the in-process PyWry FastMCP server.  Bundle the
    # three PyWry skill sheets that describe the surface this demo
    # exercises: the TradingView chart tool API, how the chat widget
    # routes messages + attachments + tool-call cards, and the event
    # system that plumbs it all together.
    from pywry.mcp import skills as _skills_pkg

    skills_root = pathlib.Path(_skills_pkg.__file__).parent
    skill_files = [
        str(skills_root / "tvchart" / "SKILL.md"),
        str(skills_root / "chat_agent" / "SKILL.md"),
        str(skills_root / "events" / "SKILL.md"),
    ]
    missing = [p for p in skill_files if not pathlib.Path(p).is_file()]
    if missing:
        raise RuntimeError(f"Missing skill files: {missing}")

    provider = DeepagentProvider(
        model=f"nvidia:{initial_model}",
        tools=[],
        mcp_servers=mcp_servers,
        system_prompt=CHART_SYSTEM_PROMPT,
        # Fully override the general-purpose PyWry prompt.
        replace_system_prompt=True,
        skills=skill_files,
        # Multi-step requests + write_todos bookkeeping easily consume
        # 15-25 graph steps; give the agent headroom so a 3-5-action
        # chain doesn't hit the default 50-step ceiling mid-plan.
        recursion_limit=150,
    )

    def _build_or_raise(model_name: str) -> Any:
        provider._model = f"nvidia:{model_name}"
        agent = provider._build_agent()
        if agent is None or not hasattr(agent, "astream_events"):
            msg = (
                f"Model '{model_name}' did not produce a streaming Deep Agent. "
                "Install/upgrade deepagents and langchain-nvidia-ai-endpoints, "
                "and pick a valid NVIDIA chat model."
            )
            raise RuntimeError(msg)
        return agent

    try:
        provider._agent = _build_or_raise(initial_model)
    except Exception as exc:
        sys.exit(
            "Failed to initialize Deep Agent.\n"
            "Install dependencies: pip install deepagents langchain-nvidia-ai-endpoints\n"
            f"Details: {exc}"
        )

    def on_settings_change(key: str, value: Any) -> None:
        if key == "model":
            prev_model = provider._model
            prev_agent = provider._agent
            try:
                provider._agent = _build_or_raise(str(value))
            except Exception as exc:
                provider._model = prev_model
                provider._agent = prev_agent
                print(f"[deepagent] model switch failed: {exc}")

    chat = ChatManager(
        provider=provider,
        welcome_message=(
            "I'm connected to the TradingView chart with live yFinance data. "
            "Type **@chart** in your message to attach the chart so I know "
            "which widget to operate on, then ask me to switch tickers, "
            "change the timeframe, add indicators, draw markers, etc."
        ),
        toolbar_width="420px",
        toolbar_min_width="320px",
        enable_context=True,
        settings=[
            SettingsItem(
                id="model",
                label="Model",
                type="select",
                value=initial_model,
                options=model_ids,
            ),
            SettingsItem(
                id="temperature",
                label="Temperature",
                type="range",
                value=0.7,
                min=0.0,
                max=2.0,
                step=0.1,
            ),
            SettingsItem(id="sep1", type="separator"),
            SettingsItem(id="clear-history", label="Clear History", type="action"),
        ],
        on_settings_change=on_settings_change,
    )

    chart_toolbars = build_tvchart_toolbars(
        intervals=SUPPORTED_RESOLUTIONS,
        selected_interval="1d",
    )

    marquee_toolbar, marquee_css = build_marquee(symbol)
    chart_toolbars.insert(0, marquee_toolbar)

    merged_callbacks: dict[str, Any] = {
        **datafeed_callbacks,
        **chat.callbacks(),
    }

    widget = app.show_tvchart(
        # Assign the TV component instance a user-chosen name — every
        # tvchart event now carries ``chartId: "chart"``, and the same
        # string is what the agent's ``@chart`` context attachment
        # routes against.  Without this, ``chart_id`` defaults to a
        # random ``tvchart_<hex>``.
        chart_id=CHART_COMPONENT_ID,
        use_datafeed=True,
        symbol=symbol,
        resolution="1d",
        title="PyWry \u2014 LangChain NVIDIA Deep Agent + TradingView Chart",
        width=1600,
        height=900,
        chart_options={"timeScale": {"secondsVisible": False}},
        toolbars=[*chart_toolbars, chat.toolbar()],
        callbacks=merged_callbacks,
        inline_css=marquee_css,
    )

    chat.bind(widget)
    # Register the TV chart component as an @-mentionable context
    # source.  The first arg is the component id (matches
    # ``chart_id`` above); the second is the label shown in the
    # popup.  When the user types ``@chart`` the chat manager attaches
    # a block whose header includes that component id, so the agent
    # knows exactly which chart instance the user means.
    chat.register_context_source(CHART_COMPONENT_ID, "Trading chart")

    try:
        app.block()
    finally:
        streamer.stop()
        stop_mcp_server()


if __name__ == "__main__":
    main()
