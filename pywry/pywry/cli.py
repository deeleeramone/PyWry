"""Command-line interface for PyWry configuration management."""

from __future__ import annotations

import argparse
import sys

from pathlib import Path
from typing import TYPE_CHECKING

from .config import _REDACTED, _SENSITIVE_FIELDS


if TYPE_CHECKING:
    from .config import PyWrySettings


def main() -> int:
    """Run the main CLI entry point.

    Returns
    -------
    int
        Exit code.
    """
    parser = argparse.ArgumentParser(
        prog="pywry",
        description="PyWry configuration and development tools",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # config command
    config_parser = subparsers.add_parser(
        "config",
        help="Show or export configuration",
    )
    config_group = config_parser.add_mutually_exclusive_group()
    config_group.add_argument(
        "--show",
        action="store_true",
        help="Show current configuration with sources",
    )
    config_group.add_argument(
        "--toml",
        action="store_true",
        help="Export configuration as TOML",
    )
    config_group.add_argument(
        "--env",
        action="store_true",
        help="Export configuration as environment variables",
    )
    config_group.add_argument(
        "--sources",
        action="store_true",
        help="Show configuration file sources",
    )
    config_parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output file path (default: stdout)",
    )

    # init command
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a pywry.toml configuration file",
    )
    init_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite existing configuration file",
    )
    init_parser.add_argument(
        "--path",
        "-p",
        type=str,
        default="pywry.toml",
        help="Path for configuration file (default: pywry.toml)",
    )

    # mcp command
    mcp_parser = subparsers.add_parser(
        "mcp",
        help="Run the MCP (Model Context Protocol) server for AI agent integration",
    )
    mcp_parser.add_argument(
        "--transport",
        "-t",
        type=str,
        choices=["stdio", "sse"],
        default=None,
        help="Transport type: 'stdio' for CLI/Claude Desktop, 'sse' for HTTP (uses config default)",
    )
    mcp_parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=None,
        help="Port for SSE transport (uses config default)",
    )
    mcp_parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host for SSE transport (uses config default)",
    )
    mcp_parser.add_argument(
        "--name",
        type=str,
        default=None,
        help="MCP server name (uses config default)",
    )
    mcp_parser.add_argument(
        "--headless",
        action="store_true",
        default=None,
        help="Run in headless mode (inline widgets via browser)",
    )
    mcp_parser.add_argument(
        "--native",
        action="store_true",
        default=None,
        help="Run in native mode (desktop windows)",
    )

    args = parser.parse_args()

    if args.command == "config":
        return handle_config(args)
    if args.command == "init":
        return handle_init(args)
    if args.command == "mcp":
        return handle_mcp(args)
    parser.print_help()
    return 0


def handle_config(args: argparse.Namespace) -> int:
    """Handle the config command.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command line arguments.

    Returns
    -------
    int
        Exit code.
    """
    from .config import PyWrySettings

    settings = PyWrySettings()

    if args.sources:
        return show_config_sources()

    if args.toml:
        output = settings.to_toml()
    elif args.env:
        output = settings.to_env()
    elif args.show:
        output = format_config_show(settings)
    else:
        output = format_config_show(settings)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Configuration written to {args.output}")
    else:
        print(output)

    return 0


def handle_init(args: argparse.Namespace) -> int:
    """Handle the init command.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command line arguments.

    Returns
    -------
    int
        Exit code.
    """
    from .config import PyWrySettings

    path = Path(args.path)

    if path.exists() and not args.force:
        print(f"Error: {path} already exists. Use --force to overwrite.", file=sys.stderr)
        return 1

    settings = PyWrySettings()
    toml_content = settings.to_toml()

    # Add header comment
    header = """# PyWry Configuration File
# Documentation: https://github.com/openbb/pywry
#
# Environment variables can override any setting:
#   PYWRY_CSP__DEFAULT_SRC="'self'"
#   PYWRY_THEME__DARK_BG="#000000"
#   PYWRY_TIMEOUT__STARTUP=30.0
#   PYWRY_WINDOW__TOOLBAR_POSITION="left"
#   PYWRY_HOT_RELOAD__ENABLED=true
#
# Use nested keys with __ (double underscore) delimiter.

"""
    path.write_text(header + toml_content, encoding="utf-8")
    print(f"Created {path}")

    return 0


def handle_mcp(args: argparse.Namespace) -> int:
    """Handle the mcp command.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command line arguments.

    Returns
    -------
    int
        Exit code.
    """
    try:
        from .mcp import run_server
    except ImportError as e:
        print(
            f"Error: MCP SDK not installed. Install with: pip install mcp\n{e}",
            file=sys.stderr,
        )
        return 1

    from .config import get_settings

    settings = get_settings()
    mcp_config = settings.mcp

    # CLI args override config (if provided)
    transport = args.transport if args.transport is not None else mcp_config.transport
    port = args.port if args.port is not None else mcp_config.port
    host = args.host if args.host is not None else mcp_config.host

    # Apply name override to the config object
    if args.name is not None:
        mcp_config = mcp_config.model_copy(update={"name": args.name})

    # Handle headless mode: CLI flags override config, which overrides PYWRY_HEADLESS env
    import os

    if args.headless:
        headless = True
    elif args.native:
        headless = False
    elif os.environ.get("PYWRY_HEADLESS") is not None:
        # Env var takes precedence over config for backwards compatibility
        headless = os.environ.get("PYWRY_HEADLESS", "0") == "1"
    else:
        headless = mcp_config.headless

    try:
        run_server(
            transport=transport,
            port=port,
            host=host,
            headless=headless,
            settings=mcp_config,
        )
    except KeyboardInterrupt:
        print("\nMCP server stopped.")
    except Exception as e:
        print(f"Error running MCP server: {e}", file=sys.stderr)
        return 1

    return 0


def show_config_sources() -> int:
    """Show configuration file sources and their status.

    Returns
    -------
    int
        Exit code.
    """
    sources = [
        ("Built-in defaults", "Always loaded", True),
        (
            "~/.config/pywry/config.toml",
            str(Path.home() / ".config" / "pywry" / "config.toml"),
            None,
        ),
        ("pyproject.toml [tool.pywry]", "pyproject.toml", None),
        ("./pywry.toml", "pywry.toml", None),
        ("Environment variables", "PYWRY_* vars", None),
    ]

    print("Configuration Sources (in order of precedence):\n")
    print(f"{'Source':<40} {'Status':<15} {'Path'}")
    print("-" * 80)

    for name, path_str, forced_status in sources:
        if forced_status is True:
            status = "✓ Active"
            path_display = ""
        elif forced_status is False:
            status = "✗ Not found"
            path_display = path_str
        # Check if file exists
        elif name == "Environment variables":
            import os

            pywry_vars = [k for k in os.environ if k.startswith("PYWRY_")]
            if pywry_vars:
                status = f"✓ {len(pywry_vars)} vars"
                path_display = ", ".join(pywry_vars[:3])
                if len(pywry_vars) > 3:
                    path_display += "..."
            else:
                status = "✗ No vars"
                path_display = ""
        else:
            path = Path(path_str).expanduser()
            if path.exists():
                status = "✓ Found"
                path_display = str(path)
            else:
                status = "✗ Not found"
                path_display = str(path)

        print(f"{name:<40} {status:<15} {path_display}")

    print("\nNote: Later sources override earlier ones.")
    return 0


def format_config_show(settings: PyWrySettings) -> str:
    """Format configuration for display.

    Parameters
    ----------
    settings : PyWrySettings
        The settings object to format.

    Returns
    -------
    str
        Formatted configuration string.
    """
    lines = []
    lines.append("PyWry Configuration\n" + "=" * 40 + "\n")

    sections = [
        ("csp", settings.csp),
        ("theme", settings.theme),
        ("timeout", settings.timeout),
        ("asset", settings.asset),
        ("log", settings.log),
        ("window", settings.window),
        ("hot_reload", settings.hot_reload),
        ("server", settings.server),
        ("deploy", settings.deploy),
        ("mcp", settings.mcp),
    ]

    for section_name, section in sections:
        if lines[-1] != "":
            lines.append("")
        lines.append(f"[{section_name}]")
        for field, value in section.model_dump(exclude=_SENSITIVE_FIELDS).items():
            lines.append(f"  {field} = {value!r}")
        lines.extend(
            f"  {rn} = '{_REDACTED}'"
            for rn in sorted(_SENSITIVE_FIELDS & section.model_fields.keys())
        )

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
