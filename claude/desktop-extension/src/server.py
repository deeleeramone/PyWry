"""Entry point for the PyWry MCP Bundle (.mcpb) loaded by Claude Desktop.

Claude Desktop's `uv` runtime resolves `pywry[mcp]` from the bundled
`pyproject.toml`, then invokes this file. We re-enter the existing
`pywry.mcp.__main__:main` so all 66+ tools, resources, and skill
loaders stay in a single source tree.
"""

import sys

from pywry.mcp.__main__ import main


if __name__ == "__main__":
    sys.argv = ["pywry-mcp", "--transport", "stdio"]
    main()
