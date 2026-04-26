# Releasing the pywry plugin

Step-by-step for cutting a new version. Assumes `main` is up to date
with everything the release should ship.

## 1. Decide the version bump

Follow the policy in [claude/CONTRIBUTING.md](../../CONTRIBUTING.md#versioning).
Summary:

- Patch: bug fix, doc, tightening an existing skill.
- Minor: new command / skill / agent / hook / MCP tool.
- Major: rename, remove, breaking contract change.

## 2. Update the version in all three manifests

Edit:

1. [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) → `"version": "…"`
2. [`claude/.claude-plugin/marketplace.json`](../../.claude-plugin/marketplace.json)
   → `plugins[name=pywry].version`
3. [`claude/desktop-extension/manifest.json`](../../desktop-extension/manifest.json)
   → `"version": "…"`

All three must match. `claude/scripts/build_distributions.py` fails fast
on drift, and CI enforces it.

## 3. Update the changelog

Edit [CHANGELOG.md](CHANGELOG.md):

- Move everything from `## [Unreleased]` into a new
  `## [<version>] — <YYYY-MM-DD>` section.
- Put an empty `## [Unreleased]` back at the top.
- Keep sub-headers (`### Added`, `### Changed`, `### Fixed`,
  `### Removed`, `### Documentation`).

## 4. Commit and merge to main

```bash
git add claude/plugins/pywry/.claude-plugin/plugin.json \
        claude/.claude-plugin/marketplace.json \
        claude/desktop-extension/manifest.json \
        claude/plugins/pywry/CHANGELOG.md
git commit -m "Release claude/plugins/pywry v<version>"
```

Open a PR, get it merged to `main`. That's the last manual step.

## 5. Automatic: tag, build, and release

Once the version-bump commit lands on `main`,
[`.github/workflows/release-claude-artifacts.yml`](../../../.github/workflows/release-claude-artifacts.yml)
runs and:

1. Reads the new version from `plugin.json`.
2. Skips if `claude-pywry-v<version>` already exists (idempotent).
3. Runs `claude/scripts/build_distributions.py` (which re-verifies
   that all three manifests are in sync — fails the workflow if not).
4. Tags the merge commit `claude-pywry-v<version>`.
5. Creates the GitHub release with the changelog section as notes
   and `pywry-cowork.plugin` + `pywry.mcpb` attached.

Tag prefix `claude-pywry-v` keeps these distinct from PyWry Python
package tags (`v2.0.0` etc.), so releases in the two trees don't
collide.

To run the build locally before opening the PR:

```bash
python claude/scripts/build_distributions.py
```

To re-run the release (e.g. after a transient failure), trigger
`Release Claude artifacts` via `workflow_dispatch` from the Actions
tab — the tag-existence check makes it safe to repeat.

## 6. Announce

Post the install command to the relevant channels:

```
/plugin marketplace add deeleeramone/PyWry --path claude/.claude-plugin/marketplace.json
/plugin install pywry@pywry --version claude-pywry-v<version>
```

## 7. Verify

In a fresh Claude Code session:

- `/mcp` lists `pywry` as connected.
- `/pywry:doctor` reports green.
- `/mcp tools pywry` shows ≥ 66 tools including `get_widget_app`.
