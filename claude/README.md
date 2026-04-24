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
│   └── pywry/                   # The canonical PyWry plugin
│       ├── .claude-plugin/plugin.json
│       ├── .mcp.json            # Declares the `pywry` MCP server
│       ├── agents/              # `pywry-builder` subagent
│       ├── commands/            # /pywry:doctor, /pywry:scaffold, /pywry:examples
│       ├── hooks/               # PostToolUse ruff format hook
│       ├── skills/              # pywry-orientation skill
│       ├── CHANGELOG.md
│       └── README.md
├── CONTRIBUTING.md              # How to add / maintain plugins here
└── README.md                    # (this file)
```

Adding a sibling plugin later is a file-system operation: create
`claude/plugins/<name>/`, add a `plugin.json`, and append an entry to
`claude/.claude-plugin/marketplace.json`.

## Installing the plugin

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
