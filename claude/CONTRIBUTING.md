# Contributing to the PyWry Claude Code plugin

This document covers the mechanics of changing anything under `claude/`.
For general PyWry development see the top-level [CLAUDE.md](../CLAUDE.md)
and the PyWry contributing guide.

## What lives here

- **`claude/.claude-plugin/marketplace.json`** — the single, canonical
  marketplace manifest for this repo. It lists every plugin under
  `claude/plugins/*`. Discovered automatically when a Claude Code user
  adds `deeleeramone/PyWry --path claude/.claude-plugin/marketplace.json`
  as a marketplace.
- **`claude/plugins/<name>/`** — one plugin each. Every plugin has its
  own `.claude-plugin/plugin.json`, `.mcp.json`, assets, CHANGELOG, and
  README.

## Versioning

Every plugin follows [semver](https://semver.org/) independently of the
PyWry Python package.

| Bump | When |
|---|---|
| **Patch** (0.1.0 → 0.1.1) | Bug fixes, doc tweaks, tightening a skill, renaming an internal helper |
| **Minor** (0.1.0 → 0.2.0) | New slash command, new skill, new subagent, new hook, new MCP tool surfaced |
| **Major** (0.1.0 → 1.0.0) | Renaming the plugin, changing the marketplace name, removing a command/skill/tool, bumping the minimum required PyWry version |

The version appears in **two** places and they **must match**:

1. `claude/plugins/<name>/.claude-plugin/plugin.json` → `version`
2. `claude/.claude-plugin/marketplace.json` → `plugins[…].version`

CI ([.github/workflows/plugin-manifest.yml](../.github/workflows/plugin-manifest.yml))
fails PRs that leave those out of sync or change any `claude/plugins/<name>/`
file without bumping the plugin's version.

## Release checklist

Use [RELEASING.md](plugins/pywry/RELEASING.md) for the step-by-step —
summary below:

1. Land all pending changes on `main`.
2. Bump the version in both manifest files.
3. Update `claude/plugins/<name>/CHANGELOG.md` with the release notes
   (keep a `## [Unreleased]` section at the top).
4. Commit with a message like
   `Release claude/plugins/pywry v0.2.0`.
5. Tag:
   ```bash
   git tag -a plugin-pywry-v0.2.0 -m "pywry plugin v0.2.0"
   git push origin plugin-pywry-v0.2.0
   ```
6. Users pin with `/plugin install pywry@pywry --version plugin-pywry-v0.2.0`
   to avoid tracking `main`.

## Adding a new plugin

```
claude/plugins/<new-plugin-name>/
├── .claude-plugin/
│   └── plugin.json           # {name, version, description, author, ...}
├── .mcp.json                 # (optional) MCP server declaration
├── agents/                   # (optional)
├── commands/                 # (optional)
├── hooks/                    # (optional)
├── skills/                   # (optional)
├── README.md
└── CHANGELOG.md
```

Then append an entry to `claude/.claude-plugin/marketplace.json`:

```json
{
  "name": "<new-plugin-name>",
  "source": "./plugins/<new-plugin-name>/",
  "description": "...",
  "version": "0.1.0",
  "license": "Apache-2.0",
  "homepage": "https://github.com/deeleeramone/PyWry",
  "keywords": ["..."]
}
```

CI will reject the PR if:

- `.claude-plugin/plugin.json` or `.mcp.json` is malformed JSON.
- The plugin version in the plugin manifest doesn't match the
  marketplace entry.
- A referenced skill/command/agent/hook file is missing.
- Any `source` path in `marketplace.json` doesn't exist on disk.

## Running the plugin locally during development

```bash
# From the repo root, in the worktree or main checkout:
pip install -e './pywry[dev]'                                    # install worktree pywry
/plugin marketplace add $(pwd)/claude                            # absolute path
/plugin install pywry@pywry
```

Then `/pywry:doctor` to verify.
