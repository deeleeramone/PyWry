"""PyWry MCP Server.

Complete MCP server exposing PyWry's full widget library using FastMCP:
- 25 Tools for widget creation, manipulation, and export
- 8 Skills/Prompts for context-aware guidance (loaded on-demand)
- 20+ Resources for documentation and source code access

Configuration:
    All settings can be configured via:
    - Environment variables: PYWRY_MCP__<SETTING>
    - Config files: [mcp] section in pywry.toml or pyproject.toml
    - CLI arguments (override config)

Usage:
    python -m pywry.mcp                      # stdio transport (default)
    python -m pywry.mcp --sse 8001           # SSE transport on port 8001
    python -m pywry.mcp --streamable-http 8001  # Streamable HTTP on port 8001
"""

# pylint: disable=C0415

from __future__ import annotations

import os

from collections.abc import Callable
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from fastmcp import FastMCP

    from pywry.config import MCPSettings

# PYWRY_HEADLESS=1 -> inline widgets (server mode)
# PYWRY_HEADLESS=0 or unset -> native windows (desktop mode)

try:
    from fastmcp import FastMCP  # pylint: disable=C0412

    HAS_MCP = True
except ImportError:
    HAS_MCP = False

# Type aliases
EventsDict = dict[str, list[dict[str, Any]]]
EventCallback = Callable[[Any, str, str], None]
EventCallbackFactory = Callable[[str], EventCallback]

# Module-level event storage (shared across tool calls)
_events: EventsDict = {}


def _make_event_callback(widget_id: str) -> EventCallback:
    """Create callback that stores events for MCP client retrieval.

    Parameters
    ----------
    widget_id : str
        Widget identifier.

    Returns
    -------
    EventCallback
        Callback function that stores events.

    """

    def callback(data: Any, event_type: str, label: str = "") -> None:
        if widget_id not in _events:
            _events[widget_id] = []
        _events[widget_id].append(
            {
                "event_type": event_type,
                "data": data,
                "label": label,
            }
        )

    return callback


def _create_tool_function(
    tool_name: str, schema: dict[str, Any], handle_tool: Any, events: EventsDict
) -> Callable[..., Any]:
    """Dynamically create a function with the right signature for the tool schema."""
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    # Build function parameters
    params = []
    for prop_name in properties:
        if prop_name in required:
            params.append(f"{prop_name}=None")  # Will be validated by MCP
        else:
            params.append(f"{prop_name}=None")

    params_str = ", ".join(params) if params else ""

    # Build the function code
    func_code = f'''
async def {tool_name.replace("-", "_")}({params_str}):
    """Dynamically generated tool handler."""
    import json
    kwargs = {{k: v for k, v in locals().items() if v is not None and k != "json"}}
    try:
        result = await _handle_tool("{tool_name}", kwargs, _events, _make_callback)
        return json.dumps(result, indent=2)
    except Exception:
        import traceback
        return json.dumps({{"error": traceback.format_exc()}})
'''

    # Execute to create the function
    local_vars: dict[str, Any] = {
        "_handle_tool": handle_tool,
        "_events": events,
        "_make_callback": _make_event_callback,
    }
    exec(func_code, local_vars)  # noqa: S102  # pylint: disable=W0122
    return local_vars[tool_name.replace("-", "_")]  # type: ignore


def _register_tools(mcp: FastMCP) -> None:
    """Register all tools on the FastMCP server.

    Parameters
    ----------
    mcp : FastMCP
        The FastMCP server instance.

    """
    from .handlers import handle_tool
    from .tools import get_tools

    # Register each tool from tools.py with fastmcp
    for tool in get_tools():
        tool_name = tool.name
        tool_desc = tool.description or ""
        tool_schema = tool.inputSchema

        # Create function with matching signature
        fn = _create_tool_function(tool_name, tool_schema, handle_tool, _events)
        fn.__doc__ = tool_desc

        # Register with fastmcp decorator
        mcp.tool()(fn)


def _register_skills_provider(mcp: FastMCP) -> None:
    """Register the SkillsDirectoryProvider for PyWry skills.

    Uses FastMCP's built-in SkillsDirectoryProvider to serve all skills
    in the skills/ subdirectory as MCP resources under the skill:// URI scheme.
    Each skill subdirectory containing a SKILL.md file is exposed automatically.

    Parameters
    ----------
    mcp : FastMCP
        The FastMCP server instance.

    """
    from pathlib import Path

    from fastmcp.server.providers.skills import SkillsDirectoryProvider

    skills_dir = Path(__file__).parent / "skills"
    mcp.add_provider(SkillsDirectoryProvider(roots=skills_dir, supporting_files="resources"))


def _register_component_docs(mcp: FastMCP) -> None:
    """Register component documentation resources."""
    from .docs import COMPONENT_DOCS
    from .resources import read_component_doc

    for comp_name, comp_doc in COMPONENT_DOCS.items():
        desc = comp_doc["description"]

        def make_handler(name: str, description: str) -> Callable[[], str]:
            def handler() -> str:
                return read_component_doc(name) or f"Component not found: {name}"

            handler.__doc__ = description
            return handler

        mcp.resource(f"pywry://component/{comp_name}")(make_handler(comp_name, desc))


def _register_source_resources(mcp: FastMCP) -> None:
    """Register component source code resources."""
    from .docs import COMPONENT_DOCS
    from .resources import read_source_code

    for comp_name in COMPONENT_DOCS:

        def make_handler(name: str) -> Callable[[], str]:
            def handler() -> str:
                return read_source_code(name) or f"Source not found: {name}"

            handler.__doc__ = f"Source code for {name} component"
            return handler

        mcp.resource(f"pywry://source/{comp_name}")(make_handler(comp_name))

    @mcp.resource("pywry://source/components")
    def all_components_source() -> str:
        """Source code for all PyWry toolbar components."""
        return read_source_code("components") or "No sources found"


def _register_static_resources(mcp: FastMCP) -> None:
    """Register static documentation resources."""
    from .resources import (
        export_widget_code,
        read_events_doc,
        read_quickstart_guide,
    )

    @mcp.resource("pywry://docs/events")
    def events_doc() -> str:
        """Documentation for all built-in PyWry events."""
        return read_events_doc()

    @mcp.resource("pywry://docs/quickstart")
    def quickstart_doc() -> str:
        """Getting started with PyWry widgets."""
        return read_quickstart_guide()

    @mcp.resource("pywry://export/{widget_id}")
    def export_widget_resource(widget_id: str) -> str:
        """Export a created widget as Python code."""
        return export_widget_code(widget_id) or f"Widget not found: {widget_id}"


def _register_agentic_tools(mcp: FastMCP) -> None:
    """Register agentic tools that use FastMCP Context for sampling / elicitation / progress.

    These tools go beyond the schema-driven dispatch layer by accepting a ``Context``
    parameter so they can:

    * Call ``ctx.sample()`` with structured Pydantic models for validated LLM output.
    * Call ``ctx.elicit()`` to interactively gather requirements from the user.
    * Call ``ctx.report_progress()`` to stream build progress to the client.

    Tools registered here:

    * ``plan_widget``    — LLM-plans a widget spec from a plain-English description.
    * ``build_app``      — End-to-end autonomous builder (plan → create → export code).
    * ``export_project`` — Packages existing widgets into a runnable Python project.
    * ``scaffold_app``   — Multi-turn elicitation → plan → returns WidgetPlan JSON.

    Parameters
    ----------
    mcp : FastMCP
        The FastMCP server instance.

    """
    from .agentic import build_app, export_project, plan_widget, scaffold_app

    mcp.tool()(plan_widget)
    mcp.tool()(build_app)
    mcp.tool()(export_project)
    mcp.tool()(scaffold_app)


def _register_resources(mcp: FastMCP) -> None:
    """Register all resources on the FastMCP server.

    Parameters
    ----------
    mcp : FastMCP
        The FastMCP server instance.

    """
    _register_component_docs(mcp)
    _register_source_resources(mcp)
    _register_static_resources(mcp)


def create_server(settings: MCPSettings | None = None) -> FastMCP:
    """Create and configure the MCP server with PyWry tools and skills.

    Parameters
    ----------
    settings : MCPSettings, optional
        MCP configuration settings. If None, loads from get_settings().

    Returns
    -------
    FastMCP
        Configured FastMCP server instance.

    Raises
    ------
    ImportError
        If fastmcp package is not installed.

    """
    if not HAS_MCP:
        raise ImportError("fastmcp package required: pip install fastmcp")

    # Load settings from config if not provided
    if settings is None:
        from pywry.config import get_settings

        settings = get_settings().mcp

    # Get version from package if not specified
    version = settings.version
    if version is None:
        try:
            from pywry import __version__

            version = __version__
        except ImportError:
            version = "0.1.0"

    # Build FastMCP kwargs - only server identity settings go here
    # Transport/runtime settings go to run() to avoid deprecation warnings
    fastmcp_kwargs: dict[str, Any] = {
        "name": settings.name,
        "version": version,
        "mask_error_details": settings.mask_error_details,
        "strict_input_validation": settings.strict_input_validation,
    }

    # Add instructions if provided
    if settings.instructions:
        fastmcp_kwargs["instructions"] = settings.instructions

    mcp = FastMCP(**fastmcp_kwargs)

    # Register all handlers
    _register_tools(mcp)
    _register_resources(mcp)
    _register_skills_provider(mcp)
    _register_agentic_tools(mcp)

    return mcp


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
    transport: str | None = None,
    port: int | None = None,
    host: str | None = None,
    headless: bool | None = None,
    settings: MCPSettings | None = None,
) -> None:
    """Run the MCP server.

    All parameters override the corresponding MCPSettings values.
    If not provided, values are loaded from configuration.

    Parameters
    ----------
    transport : str, optional
        Transport type: "stdio", "sse", or "streamable-http".
    port : int, optional
        Port for HTTP transports (ignored for stdio).
    host : str, optional
        Host for HTTP transports.
    headless : bool, optional
        Run in headless mode (inline widgets). If None, uses config or PYWRY_HEADLESS.
    settings : MCPSettings, optional
        MCP configuration settings. If None, loads from get_settings().

    Raises
    ------
    ValueError
        If unknown transport is specified.

    """
    import signal
    import sys

    from pywry import runtime
    from pywry.config import get_settings

    # Load settings from config if not provided
    if settings is None:
        settings = get_settings().mcp

    # CLI arguments override config settings
    effective_transport = transport or settings.transport
    effective_port = port if port is not None else settings.port
    effective_host = host or settings.host

    # Determine headless mode: CLI arg > config > env var
    if headless is None:
        # Check if env var is set (overrides config)
        env_headless = os.environ.get("PYWRY_HEADLESS")
        effective_headless = env_headless == "1" if env_headless is not None else settings.headless
    else:
        effective_headless = headless

    # Set env var so child modules also pick up the mode
    os.environ["PYWRY_HEADLESS"] = "1" if effective_headless else "0"

    def cleanup_and_exit(_signum: int | None = None, _frame: Any = None) -> None:
        """Clean up PyWry resources on shutdown."""
        print("\n[PyWry] Shutting down...", file=sys.stderr)
        if effective_headless:
            from pywry.inline import stop_server

            stop_server(timeout=2.0)
        else:
            runtime.stop()
        print("[PyWry] Cleanup complete", file=sys.stderr)
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup_and_exit)
    signal.signal(signal.SIGTERM, cleanup_and_exit)

    if effective_headless:
        _setup_headless_mode()
    else:
        print("[PyWry] Native window mode (desktop)", file=sys.stderr)

    mcp = create_server(settings)

    # Build run kwargs for transport settings
    run_kwargs: dict[str, Any] = {
        "log_level": settings.log_level,
    }

    # Use fastmcp's built-in transport handling
    if effective_transport == "stdio":
        mcp.run(**run_kwargs)
    elif effective_transport == "sse":
        mcp.run(
            transport="sse",
            host=effective_host,
            port=effective_port,
            **run_kwargs,
        )
    elif effective_transport == "streamable-http":
        mcp.run(
            transport="streamable-http",
            host=effective_host,
            port=effective_port,
            **run_kwargs,
        )
    else:
        raise ValueError(f"Unknown transport: {effective_transport}")
