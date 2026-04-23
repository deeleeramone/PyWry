---
description: Diagnose the PyWry install (Python interpreter, pywry[mcp] extra, native binary, MCP server reachability).
argument-hint: ""
---

Run the following diagnostic steps and report a green/red summary:

1. **Python interpreter** — run `python --version` and report the version. Fail if less than 3.10.
2. **PyWry importable** — run `python -c "import pywry; print(pywry.__version__)"`. Fail if `ImportError`; suggest `pip install pywry`.
3. **MCP extra installed** — run `python -c "import pywry.mcp, fastmcp; print(fastmcp.__version__)"`. Fail if `ImportError`; suggest `pip install 'pywry[dev]'` (or `pywry[all]`) — `[dev]` also pulls in `ruff` so the plugin's post‑edit format hook works.
4. **Native PyTauri binary** — run `python -c "import pytauri; print(pytauri.__file__)"` and confirm the module loads. Fail if the platform wheel is missing; link to the PyWry README's Linux system‑package note when on Linux.
5. **MCP server smoke start** — run `pywry mcp --transport stdio` in the background with a 3‑second timeout (this is the same command the plugin's `.mcp.json` launches). Confirm it starts without crashing (a clean stdio server waits on input). Kill it after. On Windows, also verify `pywry.exe` is on PATH — the plugin launches the console script rather than bare `python` to avoid the Microsoft Store Python shim.
6. **Claude Code MCP connection** — remind the user to run `/mcp` in Claude Code to confirm `pywry` is listed and connected.

For each step, print a single line: `✓ step name` or `✗ step name — reason — suggested fix`. Do not run PyWry example scripts or create files. This command is read‑only.

If all six checks pass, end with `PyWry is healthy. Try /pywry:scaffold <name> to create a new app.`
