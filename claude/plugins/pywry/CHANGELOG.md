# pywry plugin changelog

Versioning follows [semver](https://semver.org/). Format is a feature
list per release — not a delta.

## 0.1.0 — first public release

**MCP server.** `.mcp.json` launches `pywry mcp --transport stdio` and
surfaces the full PyWry MCP tool set — 66 tools covering widget
creation, manipulation, chat, TradingView charts, and the autonomous
builder. Source of truth is [pywry.mcp.tools](https://github.com/deeleeramone/PyWry/blob/main/pywry/pywry/mcp/tools.py).
Key additions driven by this release:

- `get_widget_app(widget_id)` — re-snapshot a widget as a full
  `AppArtifact` with a bumped revision.
- Widget-creating tools (`create_widget`, `show_plotly`,
  `show_dataframe`, `show_tvchart`, `create_chat_widget`)
  auto-return an `AppArtifact` alongside their JSON response in
  headless mode: self-contained HTML carried as an MCP
  `EmbeddedResource` with `mimeType: text/html` and
  `uri: pywry-app://<widget_id>/<revision>`.

**`AppArtifact` type.** New Pydantic artifact model in
`pywry.chat.artifacts` — carries self-contained HTML plus
`widget_id` / `revision`, rendered as a sandboxed iframe with a live
WebSocket bridge back to Python. Older revisions of the same widget in
chat history freeze at their last known state: their reconnect is
rejected server-side with close code `4002 Older revision
superseded`.

**Host-theme bridge.** `ws-bridge.js` responds to host theme state via
three channels, in priority order:

1. `pywry-host` postMessage from an outer page (used by the
   AppArtifact iframe bridge in PyWry's chat widget and by mcp-ui
   clients that emit their own theme signals).
2. `matchMedia('(prefers-color-scheme: dark)')` change events.
3. A 500 ms poll of `matchMedia(...).matches` — required because
   Chromium-in-Electron (Claude Preview, Claude Desktop) updates the
   query's `.matches` value but doesn't fire the `change` event.

An initial-sync pass runs one animation frame after load so Plotly
charts pick up the correct template even when the figure was rendered
without an explicit template. Fixes `__pywry_user_template__`
pollution that previously kept charts stuck on `plotly_white`.

**Orientation skill.** `skills/pywry-orientation/SKILL.md` teaches
Claude when to reach for PyWry (dashboards, Plotly charts, AG Grid
tables, TradingView charts, chat UIs, native desktop windows) and how
to navigate the 17 domain skills served by the `get_skills` MCP tool.

**Slash commands.**

- `/pywry:doctor` — runs the install health check: Python version,
  `import pywry`, `import pywry.mcp`, `fastmcp`, native PyTauri
  binary, a headless MCP handshake smoke test, and a reminder to
  verify `/mcp pywry` in Claude Code.
- `/pywry:scaffold [name] [--kind widget|chat|tvchart|dashboard]` —
  scaffolds a new runnable PyWry app.
- `/pywry:examples [name]` — lists or runs a bundled example
  headlessly.

**Subagent.** `agents/pywry-builder.md` is a specialised subagent with
a restricted tool surface for multi-step widget construction — builds
the widget via MCP tools, exports runnable Python, and keeps the main
thread's context clean during long interactions.

**Hook.** `hooks/hooks.json` registers a `PostToolUse` hook for
`Write` / `Edit` that runs `ruff format` on the changed `.py` file.
Short-circuits to a no-op when `ruff` is not on `PATH`.

**Packaging.**

- The plugin lives at `claude/plugins/pywry/` in the PyWry repo, listed
  from `claude/.claude-plugin/marketplace.json`.
- Install via `/plugin marketplace add deeleeramone/PyWry --path
  claude/.claude-plugin/marketplace.json` then `/plugin install
  pywry@pywry`.
- `pip install 'pywry[dev]'` (or `pywry[all]`) also ships the full
  plugin tree inside the wheel at `pywry/_claude_plugin/` — the bundle
  includes both `plugin.json` and a single-plugin `marketplace.json`
  so the installed location is a valid marketplace root as-is.
- New `pywry plugin-path` CLI subcommand prints the bundled plugin
  location for use with `/plugin marketplace add $(pywry plugin-path)`;
  `--marketplace` prints the `marketplace.json` path, `--check` exits
  non-zero with a clear error when the bundle is missing.
- `.mcp.json` launches the `pywry` console script (installed by pip)
  rather than `python -m pywry.mcp`, sidestepping the Microsoft Store
  `python` shim on Windows hosts where bare `python` isn't aliased to
  a real interpreter.

**Testing.** 12 dedicated tests in [pywry/tests/test_mcp_app_artifact.py](https://github.com/deeleeramone/PyWry/blob/main/pywry/tests/test_mcp_app_artifact.py)
cover the artifact model, revision bump, attach helper, handler
behaviour, and the `_format_tool_result` serialiser that emits the
`EmbeddedResource`. The 203-test MCP suite passes.

**Documentation.** Top-level README, [MkDocs MCP reference](https://deeleeramone.github.io/PyWry/mcp/index/),
[plugin install page](https://deeleeramone.github.io/PyWry/mcp/plugin/),
skills reference, and chat component docs all describe the plugin,
`AppArtifact`, and revision-freeze semantics.
