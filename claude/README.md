# `claude/` — Claude Code integration assets

Everything PyWry ships for Claude Code lives under this directory so the repo
root stays uncluttered and leaves room for future variants (additional plugins,
desktop extensions, evaluation harnesses, etc.) without restructuring.

## Layout

```
claude/
├── .claude-plugin/
│   └── marketplace.json         # Single marketplace, lists every plugin below
├── plugins/
│   └── pywry/                   # The canonical PyWry plugin (Claude Code)
│       ├── .claude-plugin/plugin.json
│       ├── .mcp.json            # Declares the `pywry` MCP server
│       ├── agents/              # `pywry-builder` subagent
│       ├── commands/            # /pywry:doctor, /pywry:scaffold, /pywry:examples
│       ├── hooks/               # PostToolUse ruff format hook
│       ├── skills/              # pywry-orientation skill
│       ├── CHANGELOG.md
│       └── README.md
├── desktop-extension/           # Claude Desktop MCP Bundle (.mcpb) source
│   ├── manifest.json            # MCPB manifest (different schema from plugin.json)
│   ├── pyproject.toml           # uv-runtime dependency spec → pywry[mcp]
│   ├── src/server.py            # Re-enters pywry.mcp.__main__:main
│   └── README.md
├── scripts/
│   └── build_distributions.py   # Builds dist/pywry-cowork.plugin and dist/pywry.mcpb
├── dist/                        # Build output (gitignored)
├── CONTRIBUTING.md              # How to add / maintain plugins here
└── README.md                    # (this file)
```

`claude/plugins/pywry/` is the single source of truth. The Cowork
`.plugin` is a build-time transform of it (with `.mcp.json` and
`hooks/` stripped); both are produced by
[`scripts/build_distributions.py`](scripts/build_distributions.py).

Adding a sibling plugin later is a file-system operation: create
`claude/plugins/<name>/`, add a `plugin.json`, and append an entry to
`claude/.claude-plugin/marketplace.json`.

## Distribution variants

PyWry ships into three Claude surfaces from this directory:

| Variant | Artifact | Where it lives | Install path |
|---|---|---|---|
| Claude Code plugin | `claude/plugins/pywry/` (directory) | GitHub marketplace, PyPI-bundled wheel, local worktree | `/plugin marketplace add deeleeramone/PyWry --path claude/.claude-plugin/marketplace.json` then `/plugin install pywry@pywry` |
| Cowork plugin | `claude/dist/pywry-cowork.plugin` (zip) | GitHub release asset; org marketplace upload | Cowork → Customize → Plugins → Upload plugin |
| Claude Desktop extension | `claude/dist/pywry.mcpb` (zip) | GitHub release asset | Open the `.mcpb` file in Claude Desktop |

Build the two zipped artifacts with:

```bash
python claude/scripts/build_distributions.py
```

The Cowork variant intentionally drops `.mcp.json` and `hooks/`
because Cowork's hosted sandbox cannot launch the local `pywry` CLI;
skills, slash commands, and the `pywry-builder` subagent still work.
The `.mcpb` ships only the MCP server (Claude Desktop has no concept
of slash commands or subagents).

## Installing the Claude Code plugin

### From GitHub (primary path)

```
/plugin marketplace add deeleeramone/PyWry --path claude/.claude-plugin/marketplace.json
/plugin install pywry@pywry
```

Prerequisite: `pip install 'pywry[dev]'` or `pywry[all]` in the Python
interpreter that `python` resolves to. The plugin's `.mcp.json` launches
the `pywry` console script installed by pip.

### From PyPI (bundled in the wheel)

`pip install 'pywry[dev]'` ships the full plugin tree inside the
Python package at `site-packages/pywry/_claude_plugin/`. A user who
already has PyWry installed for Python can register the plugin from
local disk without a network round-trip:

```
pywry plugin-path                 # → .../site-packages/pywry/_claude_plugin
pywry plugin-path --marketplace   # → .../_claude_plugin/.claude-plugin/marketplace.json
```

Then in Claude Code:

```
/plugin marketplace add $(pywry plugin-path)
/plugin install pywry@pywry
```

`pywry plugin-path --check` exits non-zero with an actionable error
message if the plugin tree is missing (e.g. an old wheel or a partial
install), so the same command slots into CI / install scripts.

### From a local worktree (plugin development)

```
/plugin marketplace add <absolute-path-to-claude-dir>
/plugin install pywry@pywry
```

The marketplace root for the `directory` source is the directory
containing `.claude-plugin/marketplace.json`, i.e. this `claude/` folder.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the versioning policy,
release checklist, and validation workflow.
