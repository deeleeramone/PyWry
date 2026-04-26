# pywry — Claude Desktop extension (`.mcpb`)

Native [Claude Desktop](https://claude.ai/download) integration for
[PyWry](https://github.com/deeleeramone/PyWry). Same 66+ MCP tools as
the Claude Code plugin, packaged as an [MCP Bundle](https://github.com/anthropics/dxt)
so Claude Desktop installs and runs it without any manual `pip` step.

## Install

1. Grab `pywry.mcpb` from the latest GitHub release (or run
   `python scripts/build_distributions.py` from the repo root to build
   it locally).
2. Open the file. Claude Desktop will show an install dialog —
   confirm to add the extension.
3. The `uv` runtime resolves `pywry[mcp]>=2.0.0` from PyPI on first
   launch. Subsequent launches reuse the cached environment.

## Verify

Open a Claude Desktop conversation and ask: *"List the pywry MCP
tools."* Claude should enumerate the `create_widget`, `show_plotly`,
`show_dataframe`, `show_tvchart`, `tvchart_*`, and `create_chat_widget`
families.

## Differences from the Claude Code plugin

This extension ships the **MCP server only**. Slash commands
(`/pywry:doctor`, `/pywry:scaffold`, `/pywry:examples`), the
`pywry-builder` subagent, the `pywry-orientation` skill, and the
`ruff format` PostToolUse hook are Claude Code surfaces and are not
expressible in the `.mcpb` format — install [the Claude Code plugin](../plugins/pywry/README.md)
if you want those.

## License

Apache-2.0, same as PyWry.
