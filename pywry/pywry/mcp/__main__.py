"""Entry point for running PyWry MCP server."""

import argparse


def main() -> None:
    """Run the MCP server with specified transport and port."""
    # pylint: disable=import-outside-toplevel
    from .server import run_server

    parser = argparse.ArgumentParser(description="PyWry MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport type (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port for SSE transport (default: 8001)",
    )
    parser.add_argument(
        "--sse",
        type=int,
        nargs="?",
        const=8001,
        help="Use SSE transport on specified port (shorthand for --transport sse --port N)",
    )

    args = parser.parse_args()

    if args.sse is not None:
        transport = "sse"
        port = args.sse
    else:
        transport = args.transport
        port = args.port

    run_server(transport=transport, port=port)


if __name__ == "__main__":
    main()
