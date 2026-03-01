"""Entry point for running PyWry MCP server and related utilities."""

import argparse


def _build_serve_parser(parser: argparse.ArgumentParser) -> None:
    """Add serve-related arguments to *parser*."""
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport type (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port for HTTP-based transports (default: 8001)",
    )
    parser.add_argument(
        "--sse",
        type=int,
        nargs="?",
        const=8001,
        help="Use SSE transport on specified port (shorthand for --transport sse --port N)",
    )
    parser.add_argument(
        "--streamable-http",
        type=int,
        nargs="?",
        const=8001,
        dest="streamable_http",
        help="Use streamable HTTP transport on specified port (shorthand for --transport streamable-http --port N)",
    )


def _handle_serve(args: argparse.Namespace) -> None:
    """Run the MCP server."""
    # pylint: disable=import-outside-toplevel
    from .server import run_server

    if args.streamable_http is not None:
        transport = "streamable-http"
        port = args.streamable_http
    elif args.sse is not None:
        transport = "sse"
        port = args.sse
    else:
        transport = args.transport
        port = args.port

    run_server(transport=transport, port=port)


def _handle_install_skills(args: argparse.Namespace) -> int:
    """Install bundled PyWry skills into vendor directories."""
    # pylint: disable=import-outside-toplevel
    from .install import ALL_TARGETS, install_skills, list_bundled_skills, print_install_results

    targets: list[str] = args.target
    if not targets:
        targets = ["all"]

    skill_names: list[str] | None = args.skills if args.skills else None
    custom_dir = args.custom_dir if hasattr(args, "custom_dir") else None

    if args.list:
        print("Bundled PyWry skills:")
        for name in list_bundled_skills():
            print(f"  {name}")
        return 0

    if args.list_targets:
        print("Supported vendor targets:")
        for name in ALL_TARGETS:
            print(f"  {name}")
        return 0

    try:
        results = install_skills(
            targets=targets,
            overwrite=args.overwrite,
            skill_names=skill_names,
            custom_dir=custom_dir,
            dry_run=args.dry_run,
        )
    except (ValueError, FileNotFoundError) as exc:
        import sys

        print(f"Error: {exc}", file=sys.stderr)
        return 1

    prefix = "[DRY RUN] " if args.dry_run else ""
    print(f"{prefix}PyWry skill install results:")
    print_install_results(results, verbose=args.verbose)
    return 0


def main() -> None:
    """Entry point for ``python -m pywry.mcp``."""
    parser = argparse.ArgumentParser(
        description="PyWry MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    # --- serve subcommand (also the default when no subcommand given) ---
    serve_parser = subparsers.add_parser(
        "serve",
        help="Run the MCP server (default when no subcommand is given)",
    )
    _build_serve_parser(serve_parser)

    # Add top-level serve flags too so ``python -m pywry.mcp --transport stdio`` still works
    _build_serve_parser(parser)

    # --- install-skills subcommand ---
    install_parser = subparsers.add_parser(
        "install-skills",
        help="Install bundled PyWry skills into vendor skill directories",
    )
    install_parser.add_argument(
        "--target",
        "-t",
        nargs="+",
        default=[],
        metavar="VENDOR",
        help=(
            "Vendor(s) to install into: claude, cursor, vscode, copilot, codex, "
            "gemini, goose, opencode, or 'all' (default: all)"
        ),
    )
    install_parser.add_argument(
        "--skills",
        nargs="+",
        default=None,
        metavar="SKILL",
        help="Specific skill names to install (default: all bundled skills)",
    )
    install_parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Overwrite existing skill directories (default: skip existing)",
    )
    install_parser.add_argument(
        "--custom-dir",
        default=None,
        dest="custom_dir",
        metavar="PATH",
        help="Also install into this custom directory path",
    )
    install_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        dest="dry_run",
        help="Show what would be installed without writing any files",
    )
    install_parser.add_argument(
        "--list",
        action="store_true",
        default=False,
        help="List all bundled skill names and exit",
    )
    install_parser.add_argument(
        "--list-targets",
        action="store_true",
        default=False,
        dest="list_targets",
        help="List all supported vendor targets and exit",
    )
    install_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Print per-skill status in results",
    )

    args = parser.parse_args()

    if args.subcommand == "install-skills":
        import sys

        sys.exit(_handle_install_skills(args))
    else:
        # Default: run the MCP server (subcommand == "serve" or None)
        _handle_serve(args)


if __name__ == "__main__":
    main()
