# Claude Code Plugin

PyWry ships as a first-party [Claude Code](https://claude.com/claude-code)
plugin under [`claude/plugins/pywry/`](https://github.com/deeleeramone/PyWry/tree/main/claude/plugins/pywry)
in the repository. Installing it configures the MCP server, an
orientation skill, slash commands, a subagent, and a post-edit hook in
one `/plugin install` call.

## What the plugin ships

| Surface | Detail |
|:---|:---|
| **MCP server** | `pywry mcp --transport stdio` — 66 tools including widget creation, the full `tvchart_*` family, chat, resources, and `get_widget_app` for [AppArtifact](index.md#appartifact-rich-inline-previews) rendering |
| **Orientation skill** | `pywry-orientation` — teaches the agent when to reach for PyWry vs. hand-writing a framework app, and how to call `get_skills` for the 17 domain references |
| **Slash commands** | `/pywry:doctor`, `/pywry:scaffold`, `/pywry:examples` |
| **Subagent** | `pywry-builder` — specialised for multi-step widget construction |
| **Hook** | `PostToolUse` on `Edit` / `Write` → `ruff format` on touched `.py` files (no-op when `ruff` is not on PATH) |

## Install

### From GitHub (primary)

```
/plugin marketplace add deeleeramone/PyWry --path claude/.claude-plugin/marketplace.json
/plugin install pywry@pywry
```

The repo's [`claude/.claude-plugin/marketplace.json`](https://github.com/deeleeramone/PyWry/blob/main/claude/.claude-plugin/marketplace.json)
lists every plugin under `claude/plugins/`; the `pywry` entry resolves
to [`claude/plugins/pywry/`](https://github.com/deeleeramone/PyWry/tree/main/claude/plugins/pywry).

**Prerequisite:** `pip install 'pywry[dev]'` (or `pywry[all]`) in the
Python interpreter that `python` resolves to — the plugin's `.mcp.json`
launches the `pywry` console script installed by pip.

Pin to a specific release:

```
/plugin install pywry@pywry --version plugin-pywry-v0.1.0
```

Without a version, the install tracks `main`.

### From PyPI (bundled in the wheel)

`pip install 'pywry[dev]'` ships the complete plugin tree inside the
Python package at `site-packages/pywry/_claude_plugin/`. A user who
already has PyWry installed for Python can register the plugin from
local disk without a network round-trip:

```
pywry plugin-path                 # prints the plugin root directory
pywry plugin-path --marketplace   # prints the marketplace.json path
pywry plugin-path --check         # non-zero exit if the bundle is missing
```

Then in Claude Code:

```
/plugin marketplace add $(pywry plugin-path)
/plugin install pywry@pywry
```

### From a local worktree (plugin development)

```
/plugin marketplace add /absolute/path/to/PyWry/claude
/plugin install pywry@pywry
```

The marketplace root for `directory` sources is the directory
containing `.claude-plugin/marketplace.json`.

## Verify

After install:

```
/mcp                       # should list pywry as connected
/pywry:doctor              # runs the health-check pipeline
/mcp tools pywry | head    # enumerates the tool surface
```

## Monorepo layout for future plugins

`claude/.claude-plugin/marketplace.json` is the single marketplace
manifest for the whole repo. To add a second plugin later, drop its
tree under `claude/plugins/<name>/` and append a plugins entry to the
marketplace — no root-level rearrangement needed.

See [the `claude/` README](https://github.com/deeleeramone/PyWry/blob/main/claude/README.md)
and [CONTRIBUTING](https://github.com/deeleeramone/PyWry/blob/main/claude/CONTRIBUTING.md)
for the layout spec, versioning policy, and release checklist.

## Troubleshooting

| Symptom | Fix |
|:---|:---|
| `/pywry:doctor` reports `fastmcp` missing | `pip install 'pywry[dev]'` (or `pywry[all]`) in the interpreter `python` resolves to |
| MCP server fails to start on Windows with "Python was not found" | The Microsoft Store `python` shim is on PATH; either install CPython from python.org or use a virtual env. The plugin's `.mcp.json` already launches the `pywry` console script to avoid this, but your shell must still have the `pywry` script on PATH |
| Chart doesn't match host theme | Confirmed fixed in plugin v0.1.0. Older installs can `/plugin update pywry@pywry` |
| Hook ran `ruff format` on an unwanted file | Remove the hook from `claude/plugins/pywry/hooks/hooks.json` or disable hooks for the plugin in Claude Code settings |
