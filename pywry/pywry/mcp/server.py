"""PyWry MCP Server.

Complete MCP server exposing PyWry's full widget library:
- 25 Tools for widget creation, manipulation, and export
- 8 Skills/Prompts for context-aware guidance (loaded on-demand)
- 20+ Resources for documentation and source code access

Usage:
    python -m pywry.mcp              # stdio transport (default)
    python -m pywry.mcp --sse 8001   # SSE transport on port 8001
"""

from __future__ import annotations

import json
import os

from collections.abc import Callable
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from mcp.server import Server
    from mcp.types import TextContent

# PYWRY_HEADLESS=1 -> inline widgets (server mode)
# PYWRY_HEADLESS=0 or unset -> native windows (desktop mode)

try:
    from mcp.server import Server
    from mcp.types import (
        GetPromptResult,
        Prompt,
        Resource,
        ResourceTemplate,
        TextContent,
        Tool,
    )

    HAS_MCP = True
except ImportError:
    HAS_MCP = False

# Import from submodules - after try/except block is intentional
# pylint: disable=wrong-import-position
from .handlers import handle_tool
from .prompts import get_prompt_content, get_prompts
from .resources import get_resource_templates, get_resources, read_resource
from .tools import get_tools


# pylint: enable=wrong-import-position

EventsDict = dict[str, list[dict[str, Any]]]
EventCallback = Callable[[Any, str, str], None]
EventCallbackFactory = Callable[[str], EventCallback]


def _make_event_callback(events: EventsDict, widget_id: str) -> EventCallback:
    """Create callback that stores events for MCP client retrieval.

    Parameters
    ----------
    events : EventsDict
        Event storage dictionary.
    widget_id : str
        Widget identifier.

    Returns
    -------
    EventCallback
        Callback function that stores events.

    """

    def callback(data: Any, event_type: str, label: str = "") -> None:
        if widget_id not in events:
            events[widget_id] = []
        events[widget_id].append(
            {
                "event_type": event_type,
                "data": data,
                "label": label,
            }
        )

    return callback


def _register_handlers(server: Server, events: EventsDict) -> None:
    """Register all MCP handlers on the server.

    Parameters
    ----------
    server : Server
        The MCP server instance.
    events : EventsDict
        Event storage dictionary.

    """

    def make_callback(wid: str) -> EventCallback:
        return _make_event_callback(events, wid)

    @server.list_tools()  # type: ignore[untyped-decorator, no-untyped-call]
    async def list_tools() -> list[Tool]:
        return get_tools()

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        try:
            result = await handle_tool(name, arguments, events, make_callback)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as e:
            import traceback

            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": str(e), "traceback": traceback.format_exc()}),
                )
            ]

    @server.list_prompts()  # type: ignore[untyped-decorator, no-untyped-call]
    async def list_prompts() -> list[Prompt]:
        return get_prompts()

    @server.get_prompt()  # type: ignore[untyped-decorator, no-untyped-call]
    async def get_prompt(name: str, _arguments: dict[str, str] | None = None) -> GetPromptResult:
        result = get_prompt_content(name)
        if result is None:
            raise ValueError(f"Unknown prompt: {name}")
        return result

    @server.list_resources()  # type: ignore[untyped-decorator, no-untyped-call]
    async def list_resources() -> list[Resource]:
        return get_resources()

    @server.read_resource()  # type: ignore[untyped-decorator, no-untyped-call]
    async def resource_reader(uri: Any) -> str:
        uri_str = str(uri)
        content = read_resource(uri_str)
        if content is None:
            raise ValueError(f"Resource not found: {uri_str}")
        return content

    @server.list_resource_templates()  # type: ignore[untyped-decorator, no-untyped-call]
    async def list_resource_templates_handler() -> list[ResourceTemplate]:
        return get_resource_templates()


def create_server(name: str = "pywry-widgets") -> Server:
    """Create and configure the MCP server with PyWry tools and skills.

    Parameters
    ----------
    name : str, optional
        MCP server name. Default is "pywry-widgets".

    Returns
    -------
    Server
        Configured MCP server instance.

    Raises
    ------
    ImportError
        If mcp package is not installed.

    """
    if not HAS_MCP:
        raise ImportError("mcp package required: pip install mcp")

    server = Server(name)
    events: EventsDict = {}
    _register_handlers(server, events)
    return server


def _run_stdio(server: Server) -> None:
    """Run MCP server with stdio transport."""
    import asyncio

    from mcp.server.stdio import stdio_server

    async def main() -> None:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    asyncio.run(main())


def _run_sse(server: Server, host: str, port: int) -> None:
    """Run MCP server with SSE transport."""
    import uvicorn

    from mcp.server.sse import SseServerTransport

    sse = SseServerTransport("/messages/")

    async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            return

        path = scope["path"]
        if path == "/sse" and scope["method"] == "GET":
            async with sse.connect_sse(scope, receive, send) as streams:
                await server.run(streams[0], streams[1], server.create_initialization_options())
        elif path.startswith("/messages") and scope["method"] == "POST":
            await sse.handle_post_message(scope, receive, send)
        else:
            await send(
                {
                    "type": "http.response.start",
                    "status": 404,
                    "headers": [[b"content-type", b"text/plain"]],
                }
            )
            await send({"type": "http.response.body", "body": b"Not Found"})

    uvicorn.run(app, host=host, port=port)


def _setup_headless_mode() -> None:
    """Start inline widget server for headless mode."""
    import sys

    from pywry.inline import _start_server as start_pywry_server, _state as pywry_state

    start_pywry_server()
    print(
        f"[PyWry] Inline widget server: http://{pywry_state.host}:{pywry_state.port}",
        file=sys.stderr,
    )


def run_server(
    transport: str = "stdio",
    port: int = 8001,
    host: str = "127.0.0.1",
    name: str = "pywry-widgets",
    headless: bool | None = None,
) -> None:
    """Run the MCP server.

    Parameters
    ----------
    transport : str, optional
        Transport type: "stdio" or "sse". Default is "stdio".
    port : int, optional
        Port for SSE transport (ignored for stdio). Default is 8001.
    host : str, optional
        Host for SSE transport. Default is "127.0.0.1".
    name : str, optional
        MCP server name. Default is "pywry-widgets".
    headless : bool, optional
        Run in headless mode (inline widgets). If None, checks PYWRY_HEADLESS env var.

    Raises
    ------
    ValueError
        If unknown transport is specified.

    """
    import signal
    import sys

    from pywry import runtime

    # Determine headless mode: explicit parameter > env var > default (False)
    if headless is None:
        headless = os.environ.get("PYWRY_HEADLESS", "0") == "1"

    # Set env var so child modules also pick up the mode
    os.environ["PYWRY_HEADLESS"] = "1" if headless else "0"

    def cleanup_and_exit(_signum: int | None = None, _frame: Any = None) -> None:
        """Clean up PyWry resources on shutdown."""
        print("\n[PyWry] Shutting down...", file=sys.stderr)
        if headless:
            from pywry.inline import stop_server

            stop_server(timeout=2.0)
        else:
            runtime.stop()
        print("[PyWry] Cleanup complete", file=sys.stderr)
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup_and_exit)
    signal.signal(signal.SIGTERM, cleanup_and_exit)

    if headless:
        _setup_headless_mode()
    else:
        print("[PyWry] Native window mode (desktop)", file=sys.stderr)

    server = create_server(name)

    if transport == "stdio":
        _run_stdio(server)
    elif transport == "sse":
        _run_sse(server, host, port)
    else:
        raise ValueError(f"Unknown transport: {transport}")
